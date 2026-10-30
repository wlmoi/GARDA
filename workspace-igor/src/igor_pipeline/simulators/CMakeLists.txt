cmake_minimum_required(VERSION 3.10)
project(mock_de10_host_server CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include_directories(../protocol)

add_executable(mock_de10_host_server mock_de10_host_server.cpp)
target_link_libraries(mock_de10_host_server pthread)
