cmake_minimum_required(VERSION 3.10)
project(jetson_ai_streamer CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include_directories(../protocol)

add_executable(jetson_ai_streamer jetson_main.cpp jetson_client_adapter.cpp)
target_link_libraries(jetson_ai_streamer pthread)
