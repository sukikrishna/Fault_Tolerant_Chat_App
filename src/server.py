import logging
import queue

import grpc
import spec_pb2
import spec_pb2_grpc

from models import init_db, get_session_factory

import threading
import time
import queue
from follower_server import *
from leader_server import *


def claim_leadery(leader_state):
    """Notifies all followers that this server is now the leader.

    Args:
        leader_state (dict): State dictionary containing follower addresses and leader info.
    """

    """Informs all the followers that this server has become the new leader
    wathcout for competing leaders problem"""
    leader_id, leader_address = leader_state['leader_id'], leader_state['leader_address']
    for _, follower_address in leader_state['followers']:
        # print('trying to update follower', follower_address)
        with grpc.insecure_channel(follower_address) as channel:
            stub = spec_pb2_grpc.FollowerServiceStub(channel)
            # print(follower_address, stub, channel)
            update_leader_request = spec_pb2.NewLeaderRequest(
                new_leader_address=leader_address, new_leader_id=leader_id)
            # print(update_leader_request)
            # response = stub.SIMPLE(spec_pb2.Empty(), timeout=5)
            # print('after simple')
            response = stub.UpdateLeader(update_leader_request, timeout=5)
            # print('response', response)


def upgrade_follower(old_state):
    """Promotes a follower to a leader by initializing leader services.

    Args:
        old_state (dict): Current follower state to be upgraded.
    """
    # Upgrade the follower to a leader
    # Start the leader server
    # Start the follower server
    leader_state = old_state
    leader_state['leader_address'] = old_state['follower_address']
    leader_state['leader_id'] = old_state['follower_id']
    leader_state['update_queue'] = queue.Queue()

    # print('killing the opersor :)')
    leader_state['follower_leader_server'].stop(None)
    leader_state['follower_leader_server'].wait_for_termination()
    leader_state['follower_client_server'].stop(None)
    leader_state['follower_client_server'].wait_for_termination()

    del leader_state['follower_leader_server']
    del leader_state['follower_id']
    del leader_state['follower_address']

    # start a new leader service
    leader_follower_server = serve_leader_follower(leader_state)

    # create updater thread
    update_thread = threading.Thread(
        target=update_followers, args=(leader_state,))
    update_thread.start()

    # start a new client service
    leader_client_server = serve_leader_client(leader_state)

    claim_leadery(leader_state)

    leader_follower_server.wait_for_termination()
    leader_client_server.wait_for_termination()

    # remove from other's followers list


def check_new_leader(min_follower, follower_state):
    """Checks if the new leader is alive and updates follower state accordingly.

    Args:
        min_follower (tuple): (ID, address) of the assumed new leader.
        follower_state (dict): The current follower state dictionary.
    """

    with grpc.insecure_channel(min_follower[1]) as channel:
        num_tries = 2
        stub = spec_pb2_grpc.LeaderServiceStub(channel)
        success = False
        for _ in range(num_tries):
            try:
                response = stub.CheckLeader(spec_pb2.Empty())
                if (response.error_code == 0):
                    print('New leader is alive')
                    follower_state['leader_address'] = min_follower[1]
                    follower_state['leader_id'] = min_follower[0]
                    success = True
                else:
                    # remove the min follower from the list
                    follower_state['followers'].remove(min_follower)
            except:
                pass
        if not success:
            print('New leader is dead')
            try:
                follower_state['followers'].remove(min_follower)
            except:
                print('Error removing the follower')
                pass

# represents a single client


def follower_heart_beat_checker(follower_state):
    """Periodically checks if the leader is alive and initiates election if not.

    Args:
        follower_state (dict): The current follower state dictionary.
    """

    while True:
        leader_address = follower_state['leader_address']
        print("Heartbeat check", leader_address)

        # Check if the leader is alive
        # If not start the election process
        with grpc.insecure_channel(leader_address) as channel:
            num_tries = 2
            success = False
            for i in range(num_tries):
                try:
                    stub = spec_pb2_grpc.LeaderServiceStub(channel)
                    heartbeat_request = spec_pb2.Empty()
                    response = stub.HeartBeat(heartbeat_request)
                    # print(response, "Leader is alive")
                    success = True
                    break
                except Exception as e:
                    # print(e)
                    if i == num_tries - 1:
                        print("Leader is not alive, starting election process.")
                        # Start the election process
            if not success:
                followers = follower_state['followers']
                min_follower = None if len(followers) == 0 else min(
                    followers, key=lambda x: int(x[0]))
                # elction policy
                # if you are smallest id become the leader
                # if not wait for a new leader and then try again
                if min_follower == None or int(server_id) < int(min_follower[0]):
                    # become the new leader
                    return upgrade_follower(follower_state)

                else:
                    # check if the new follower becomes the leader if they can't be
                    # delete them and assign yourself
                    print('Waiting for a new leader!')
                    time.sleep(10)
                    # check if the new leader is alive
                    # otherwise assume that leader is dead and remove it from
                    # your list
                    check_new_leader(min_follower, follower_state)

        time.sleep(5)


def leader_routine(
    server_id, internal_address, client_address, leader_address=None
):
    """Bootstraps the leader server and its components.

    Args:
        server_id (str): Unique server identifier.
        internal_address (str): gRPC address for internal leader-follower communication.
        client_address (str): gRPC address for client-leader communication.
        leader_address (str, optional): Address of current leader (unused for leaders).
    """

    database_url = f'sqlite:///chat_{server_id}.db'
    database_engine = init_db(database_url)

    SessionFactory = get_session_factory(database_engine)

    leader_state = {
        'leader_id': server_id,
        'leader_address': internal_address,
        'followers': [],
        'db_engine': database_engine,
        'db_session': SessionFactory,
        'update_queue': queue.Queue(),
        'client_address': client_address
    }

    # follower communication
    leader_server = serve_leader_follower(leader_state)

    # Start a separate thread to send updates to followers
    update_thread = threading.Thread(
        target=update_followers, args=(leader_state,))
    update_thread.start()

    # start client server
    clinet_server = serve_leader_client(leader_state)

    # wait for both
    leader_server.wait_for_termination()
    clinet_server.wait_for_termination()


def follower_routine(server_id, internal_address, client_address, leader_address=None):
    """Bootstraps the follower server, registers with leader, and starts heartbeat thread.

    Args:
        server_id (str): Unique server identifier.
        internal_address (str): Address used for internal leader-follower communication.
        client_address (str): gRPC address for client-follower communication.
        leader_address (str): Address of the current leader.
    """

    database_url = f'sqlite:///chat_{server_id}.db'
    database_engine = init_db(database_url, drop_tables=True)

    SessionFactory = get_session_factory(database_engine)
    logging.basicConfig()

    follower_state = {
        "followers": [],
        "leader_address": leader_address,
        "follower_id": server_id,
        "follower_address": internal_address,
        "database_engine": database_engine,
        "db_session": SessionFactory,
        'client_address': client_address,
        'db_engine': database_engine,
        'follower_client_server': None,
        'database_url': database_url,
    }

    # start internal server for follower
    follower_server = server_follower_leader(
        follower_state
    )

    follower_state['follower_leader_server'] = follower_server
    # send message to the leaders registe method
    request_update(follower_state)

    # create a thread for the heart beat checker
    heart_beat_thread = threading.Thread(
        target=follower_heart_beat_checker, args=(follower_state, ))
    heart_beat_thread.start()

    clinet_server = serve_follower_client(follower_state)
    follower_state['follower_client_server'] = clinet_server
    follower_state['heartbeat_thread'] = heart_beat_thread
    clinet_server.wait_for_termination()
    follower_server.wait_for_termination()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description="Start a chat server as a leader or a follower.")
    parser.add_argument("server_id", help="Unique server ID.")
    parser.add_argument(
        "type", choices=["leader", "follower"], help="Server type: leader or follower.")
    parser.add_argument(
        "client_address", help="Server address to communicate client in the format < host > : < port >"
    )
    parser.add_argument(
        "internal_address", help="Server address to communicate internally in the format < host > : < port >"
    )
    parser.add_argument(
        "--leader_address", help="Leader server address (required for follower servers).")

    args = parser.parse_args()

    server_id = args.server_id
    server_type = args.type
    client_address = args.client_address
    internal_address = args.internal_address
    leader_address = args.leader_address

    if server_type == "follower" and leader_address is None:
        parser.error("Follower servers require the --leader_address option.")

    if server_type == 'leader':
        leader_routine(server_id, internal_address, client_address)
    else:
        follower_routine(server_id, internal_address,
                      client_address, leader_address)

    # incase follower is upgraded to leader
    # keep the main thread alive
    # for the new leader to run
    stop_event = threading.Event()
    stop_event.wait()
