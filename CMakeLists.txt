cmake_minimum_required(VERSION 3.20)
project(VolEdge LANGUAGES CXX)

include(CTest)
find_package(Python3 REQUIRED COMPONENTS Interpreter Development.Module)

execute_process(
    COMMAND ${Python3_EXECUTABLE} -m pybind11 --cmakedir
    OUTPUT_VARIABLE pybind11_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
    COMMAND_ERROR_IS_FATAL ANY
)
find_package(pybind11 CONFIG REQUIRED)

add_library(voledge_bsm cpp/src/bsm.cpp)
target_include_directories(voledge_bsm PUBLIC cpp/include)
target_compile_features(voledge_bsm PUBLIC cxx_std_20)
set_target_properties(voledge_bsm PROPERTIES
    CXX_EXTENSIONS OFF
    POSITION_INDEPENDENT_CODE ON
)

add_executable(voledge_bsm_cli cpp/src/bsm_cli.cpp)
target_link_libraries(voledge_bsm_cli PRIVATE voledge_bsm)

add_library(voledge_american_crr cpp/src/american_crr.cpp)
target_include_directories(voledge_american_crr PUBLIC cpp/include)
target_link_libraries(voledge_american_crr PUBLIC voledge_bsm)
target_compile_features(voledge_american_crr PUBLIC cxx_std_20)
set_target_properties(voledge_american_crr PROPERTIES
    CXX_EXTENSIONS OFF
    POSITION_INDEPENDENT_CODE ON
)

add_executable(voledge_american_crr_cli cpp/src/american_crr_cli.cpp)
target_link_libraries(voledge_american_crr_cli PRIVATE voledge_american_crr)

pybind11_add_module(_voledge_native bindings/python.cpp)
target_link_libraries(_voledge_native PRIVATE voledge_bsm voledge_american_crr)
target_compile_features(_voledge_native PRIVATE cxx_std_20)
set_target_properties(_voledge_native PROPERTIES
    CXX_EXTENSIONS OFF
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/python"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/python"
)

if(MSVC)
    target_compile_options(voledge_bsm PRIVATE /W4 /WX)
    target_compile_options(voledge_bsm_cli PRIVATE /W4 /WX)
    target_compile_options(voledge_american_crr PRIVATE /W4 /WX)
    target_compile_options(voledge_american_crr_cli PRIVATE /W4 /WX)
    target_compile_options(_voledge_native PRIVATE /W4 /WX)
else()
    target_compile_options(voledge_bsm PRIVATE -Wall -Wextra -Wpedantic -Werror)
    target_compile_options(voledge_bsm_cli PRIVATE -Wall -Wextra -Wpedantic -Werror)
    target_compile_options(voledge_american_crr PRIVATE -Wall -Wextra -Wpedantic -Werror)
    target_compile_options(voledge_american_crr_cli PRIVATE -Wall -Wextra -Wpedantic -Werror)
    target_compile_options(_voledge_native PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()

add_test(
    NAME cpp_python_parity
    COMMAND
        ${CMAKE_COMMAND} -E env
        "PYTHONPATH=${CMAKE_CURRENT_SOURCE_DIR}/python"
        ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/tests/cpp_parity_check.py
        $<TARGET_FILE:voledge_bsm_cli>
)
if(WIN32)
    set(_pythonpath_separator ";")
else()
    set(_pythonpath_separator ":")
endif()
add_test(
    NAME pybind_python_parity
    COMMAND
        ${CMAKE_COMMAND} -E env
        "PYTHONPATH=${CMAKE_BINARY_DIR}/python${_pythonpath_separator}${CMAKE_CURRENT_SOURCE_DIR}/python"
        ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/tests/pybind_parity_check.py
)
set_tests_properties(pybind_python_parity PROPERTIES
    DEPENDS cpp_python_parity
)
add_test(
    NAME american_crr_python_parity
    COMMAND
        ${CMAKE_COMMAND} -E env
        "PYTHONPATH=${CMAKE_CURRENT_SOURCE_DIR}/python"
        ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/tests/american_crr_parity_check.py
        $<TARGET_FILE:voledge_american_crr_cli>
)
add_test(
    NAME pybind_american_crr_parity
    COMMAND
        ${CMAKE_COMMAND} -E env
        "PYTHONPATH=${CMAKE_BINARY_DIR}/python${_pythonpath_separator}${CMAKE_CURRENT_SOURCE_DIR}/python"
        ${Python3_EXECUTABLE}
        ${CMAKE_CURRENT_SOURCE_DIR}/tests/pybind_american_crr_parity_check.py
)
