// This file test all combinations of BSON constructor usage
BSONObj options = BSON("capped" << true << "size" << 10 * 1024 * 1024);
BSONObj options = BSON("running" << false);
BSONObj options = BSON("running" << true);
BSONObj options = BSON("_id"_sd << "test.varun"_sd
                                        << "user"_sd
                                        << "varun"
                                        << "db"_sd
                                        << "test"
                                        << "credentials"_sd << credentials << "roles"_sd
                                        << BSON_ARRAY(BSON("role"_sd << "readWrite"_sd
                                                                     << "db"_sd
                                                                     << "test"_sd)));
std::cout << "Invalid command: " << command[0] << endl;