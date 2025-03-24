# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# NO CHECKED-IN PROTOBUF GENCODE
# source: spec.proto
# Protobuf Python Version: 5.29.0
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    5,
    29,
    0,
    '',
    'spec.proto'
)
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google.protobuf import timestamp_pb2 as google_dot_protobuf_dot_timestamp__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\nspec.proto\x1a\x1fgoogle/protobuf/timestamp.proto\":\n\x14\x43reateAccountRequest\x12\x10\n\x08username\x18\x01 \x01(\t\x12\x10\n\x08password\x18\x02 \x01(\t\"O\n\x0eServerResponse\x12\x12\n\nerror_code\x18\x01 \x01(\x05\x12\x15\n\rerror_message\x18\x02 \x01(\t\x12\x12\n\nsession_id\x18\x03 \x01(\t\"M\n\"AcknowledgeReceivedMessagesRequest\x12\x12\n\nsession_id\x18\x01 \x01(\t\x12\x13\n\x0bmessage_ids\x18\x02 \x03(\x05\"2\n\x0cLoginRequest\x12\x10\n\x08username\x18\x01 \x01(\t\x12\x10\n\x08password\x18\x02 \x01(\t\">\n\x0bSendRequest\x12\n\n\x02to\x18\x01 \x01(\t\x12\x0f\n\x07message\x18\x02 \x01(\t\x12\x12\n\nsession_id\x18\x03 \x01(\t\"$\n\x10ListUsersRequest\x12\x10\n\x08wildcard\x18\x01 \x01(\t\"@\n\x15\x44\x65leteMessagesRequest\x12\x12\n\nsession_id\x18\x01 \x01(\t\x12\x13\n\x0bmessage_ids\x18\x02 \x03(\x05\"*\n\x0bUnreadCount\x12\x0c\n\x04\x66rom\x18\x01 \x01(\t\x12\r\n\x05\x63ount\x18\x02 \x01(\x05\"X\n\rUnreadSummary\x12\x1c\n\x06\x63ounts\x18\x01 \x03(\x0b\x32\x0c.UnreadCount\x12\x12\n\nerror_code\x18\x02 \x01(\x05\x12\x15\n\rerror_message\x18\x03 \x01(\t\"$\n\x0eSessionRequest\x12\x12\n\nsession_id\x18\x01 \x01(\t\"$\n\x0eReceiveRequest\x12\x12\n\nsession_id\x18\x01 \x01(\t\"3\n\x0b\x43hatRequest\x12\x12\n\nsession_id\x18\x01 \x01(\t\x12\x10\n\x08username\x18\x02 \x01(\t\"*\n\x14\x44\x65leteAccountRequest\x12\x12\n\nsession_id\x18\x01 \x01(\t\"m\n\x07Message\x12\r\n\x05\x66rom_\x18\x01 \x01(\t\x12\x0f\n\x07message\x18\x02 \x01(\t\x12\x12\n\nmessage_id\x18\x03 \x01(\x05\x12.\n\ntime_stamp\x18\x04 \x01(\x0b\x32\x1a.google.protobuf.Timestamp\"P\n\x08Messages\x12\x12\n\nerror_code\x18\x01 \x01(\x05\x12\x15\n\rerror_message\x18\x02 \x01(\t\x12\x19\n\x07message\x18\x03 \x03(\x0b\x32\x08.Message\"\x07\n\x05\x45mpty\"(\n\x04User\x12\x10\n\x08username\x18\x01 \x01(\t\x12\x0e\n\x06status\x18\x02 \x01(\t\"\x1c\n\x05Users\x12\x13\n\x04user\x18\x01 \x03(\x0b\x32\x05.User\"E\n\x10NewLeaderRequest\x12\x1a\n\x12new_leader_address\x18\x01 \x01(\t\x12\x15\n\rnew_leader_id\x18\x02 \x01(\t\"-\n\x16UpdateFollowersRequest\x12\x13\n\x0bupdate_data\x18\x01 \x01(\x0c\"H\n\x17RegisterFollowerRequest\x12\x13\n\x0b\x66ollower_id\x18\x01 \x01(\t\x12\x18\n\x10\x66ollower_address\x18\x02 \x01(\t\"r\n\x18RegisterFollowerResponse\x12\x12\n\nerror_code\x18\x01 \x01(\x05\x12\x15\n\rerror_message\x18\x02 \x01(\t\x12\x12\n\npickled_db\x18\x03 \x01(\x0c\x12\x17\n\x0fother_followers\x18\x04 \x03(\t\"+\n\x14\x41\x63\x63\x65ptUpdatesRequest\x12\x13\n\x0bupdate_data\x18\x01 \x01(\x0c\"0\n\x03\x41\x63k\x12\x12\n\nerror_code\x18\x01 \x01(\x05\x12\x15\n\rerror_message\x18\x02 \x01(\t2\xbe\x04\n\rClientAccount\x12\x37\n\rCreateAccount\x12\x15.CreateAccountRequest\x1a\x0f.ServerResponse\x12&\n\tListUsers\x12\x11.ListUsersRequest\x1a\x06.Users\x12\'\n\x05Login\x12\r.LoginRequest\x1a\x0f.ServerResponse\x12%\n\x04Send\x12\x0c.SendRequest\x1a\x0f.ServerResponse\x12)\n\x0bGetMessages\x12\x0f.ReceiveRequest\x1a\t.Messages\x12\"\n\x07GetChat\x12\x0c.ChatRequest\x1a\t.Messages\x12S\n\x1b\x41\x63knowledgeReceivedMessages\x12#.AcknowledgeReceivedMessagesRequest\x1a\x0f.ServerResponse\x12\x37\n\rDeleteAccount\x12\x15.DeleteAccountRequest\x1a\x0f.ServerResponse\x12\x30\n\x06Logout\x12\x15.DeleteAccountRequest\x1a\x0f.ServerResponse\x12\x39\n\x0e\x44\x65leteMessages\x12\x16.DeleteMessagesRequest\x1a\x0f.ServerResponse\x12\x32\n\x0fGetUnreadCounts\x12\x0f.SessionRequest\x1a\x0e.UnreadSummary2\x90\x01\n\rLeaderService\x12G\n\x10RegisterFollower\x12\x18.RegisterFollowerRequest\x1a\x19.RegisterFollowerResponse\x12\x19\n\tHeartBeat\x12\x06.Empty\x1a\x04.Ack\x12\x1b\n\x0b\x43heckLeader\x12\x06.Empty\x1a\x04.Ack2\xa5\x01\n\x0f\x46ollowerService\x12\x37\n\rAcceptUpdates\x12\x15.AcceptUpdatesRequest\x1a\x0f.ServerResponse\x12\'\n\x0cUpdateLeader\x12\x11.NewLeaderRequest\x1a\x04.Ack\x12\x30\n\x0fUpdateFollowers\x12\x17.UpdateFollowersRequest\x1a\x04.Ackb\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'spec_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_CREATEACCOUNTREQUEST']._serialized_start=47
  _globals['_CREATEACCOUNTREQUEST']._serialized_end=105
  _globals['_SERVERRESPONSE']._serialized_start=107
  _globals['_SERVERRESPONSE']._serialized_end=186
  _globals['_ACKNOWLEDGERECEIVEDMESSAGESREQUEST']._serialized_start=188
  _globals['_ACKNOWLEDGERECEIVEDMESSAGESREQUEST']._serialized_end=265
  _globals['_LOGINREQUEST']._serialized_start=267
  _globals['_LOGINREQUEST']._serialized_end=317
  _globals['_SENDREQUEST']._serialized_start=319
  _globals['_SENDREQUEST']._serialized_end=381
  _globals['_LISTUSERSREQUEST']._serialized_start=383
  _globals['_LISTUSERSREQUEST']._serialized_end=419
  _globals['_DELETEMESSAGESREQUEST']._serialized_start=421
  _globals['_DELETEMESSAGESREQUEST']._serialized_end=485
  _globals['_UNREADCOUNT']._serialized_start=487
  _globals['_UNREADCOUNT']._serialized_end=529
  _globals['_UNREADSUMMARY']._serialized_start=531
  _globals['_UNREADSUMMARY']._serialized_end=619
  _globals['_SESSIONREQUEST']._serialized_start=621
  _globals['_SESSIONREQUEST']._serialized_end=657
  _globals['_RECEIVEREQUEST']._serialized_start=659
  _globals['_RECEIVEREQUEST']._serialized_end=695
  _globals['_CHATREQUEST']._serialized_start=697
  _globals['_CHATREQUEST']._serialized_end=748
  _globals['_DELETEACCOUNTREQUEST']._serialized_start=750
  _globals['_DELETEACCOUNTREQUEST']._serialized_end=792
  _globals['_MESSAGE']._serialized_start=794
  _globals['_MESSAGE']._serialized_end=903
  _globals['_MESSAGES']._serialized_start=905
  _globals['_MESSAGES']._serialized_end=985
  _globals['_EMPTY']._serialized_start=987
  _globals['_EMPTY']._serialized_end=994
  _globals['_USER']._serialized_start=996
  _globals['_USER']._serialized_end=1036
  _globals['_USERS']._serialized_start=1038
  _globals['_USERS']._serialized_end=1066
  _globals['_NEWLEADERREQUEST']._serialized_start=1068
  _globals['_NEWLEADERREQUEST']._serialized_end=1137
  _globals['_UPDATEFOLLOWERSREQUEST']._serialized_start=1139
  _globals['_UPDATEFOLLOWERSREQUEST']._serialized_end=1184
  _globals['_REGISTERFOLLOWERREQUEST']._serialized_start=1186
  _globals['_REGISTERFOLLOWERREQUEST']._serialized_end=1258
  _globals['_REGISTERFOLLOWERRESPONSE']._serialized_start=1260
  _globals['_REGISTERFOLLOWERRESPONSE']._serialized_end=1374
  _globals['_ACCEPTUPDATESREQUEST']._serialized_start=1376
  _globals['_ACCEPTUPDATESREQUEST']._serialized_end=1419
  _globals['_ACK']._serialized_start=1421
  _globals['_ACK']._serialized_end=1469
  _globals['_CLIENTACCOUNT']._serialized_start=1472
  _globals['_CLIENTACCOUNT']._serialized_end=2046
  _globals['_LEADERSERVICE']._serialized_start=2049
  _globals['_LEADERSERVICE']._serialized_end=2193
  _globals['_FOLLOWERSERVICE']._serialized_start=2196
  _globals['_FOLLOWERSERVICE']._serialized_end=2361
# @@protoc_insertion_point(module_scope)
