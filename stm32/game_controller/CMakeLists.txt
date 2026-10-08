cmake_minimum_required(VERSION 3.22)

#
# This file is generated only once,
# and is not re-generated if converter is called multiple times.
#
# User is free to modify the file as much as necessary
#

# Setup compiler settings
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS ON)


# Define the build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE "Debug")
endif()

# Set the project name
set(CMAKE_PROJECT_NAME stm32_project)

# Enable compile command to ease indexing with e.g. clangd
set(CMAKE_EXPORT_COMPILE_COMMANDS TRUE)

# Core project settings
project(${CMAKE_PROJECT_NAME})
message("Build type: " ${CMAKE_BUILD_TYPE})

# Enable CMake support for ASM and C languages
enable_language(C ASM)

# Create an executable object type
add_executable(${CMAKE_PROJECT_NAME})

# Add STM32CubeMX generated sources
add_subdirectory(cmake/stm32cubemx)

# Link directories setup
target_link_directories(${CMAKE_PROJECT_NAME} PRIVATE
    # Add user defined library search paths
)

# -----------------------------------------------------------------------------
# User Modules Auto-Scan Configuration
# Scan all .c and .h files recursively in user directories (ap, App, modules, etc.)
# CONFIGURE_DEPENDS ensures CMake detects added/removed files automatically.
# -----------------------------------------------------------------------------
file(GLOB_RECURSE USER_SOURCES CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/ap/*.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/App/*.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/modules/*.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/Modules/*.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/bsp/*.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/driver/*.c"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/*.c"
)

# Collect all directories containing .h files
file(GLOB_RECURSE USER_HEADERS CONFIGURE_DEPENDS
    "${CMAKE_CURRENT_SOURCE_DIR}/ap/*.h"
    "${CMAKE_CURRENT_SOURCE_DIR}/App/*.h"
    "${CMAKE_CURRENT_SOURCE_DIR}/modules/*.h"
    "${CMAKE_CURRENT_SOURCE_DIR}/Modules/*.h"
    "${CMAKE_CURRENT_SOURCE_DIR}/bsp/*.h"
    "${CMAKE_CURRENT_SOURCE_DIR}/driver/*.h"
    "${CMAKE_CURRENT_SOURCE_DIR}/src/*.h"
)

set(USER_INCLUDE_DIRS 
    "${CMAKE_CURRENT_SOURCE_DIR}/ap"
    "${CMAKE_CURRENT_SOURCE_DIR}/ap/inc"
    "${CMAKE_CURRENT_SOURCE_DIR}/ap/Inc"
)
foreach(_headerFile ${USER_HEADERS})
    get_filename_component(_dir ${_headerFile} DIRECTORY)
    list(APPEND USER_INCLUDE_DIRS ${_dir})
endforeach()
if(USER_INCLUDE_DIRS)
    list(REMOVE_DUPLICATES USER_INCLUDE_DIRS)
endif()

message(STATUS ">> Found User Sources: ${USER_SOURCES}")
message(STATUS ">> Found User Include Dirs: ${USER_INCLUDE_DIRS}")

# Add sources to executable
target_sources(${CMAKE_PROJECT_NAME} PRIVATE
    ${USER_SOURCES}
)

# Add include paths
target_include_directories(${CMAKE_PROJECT_NAME} PRIVATE
    ${USER_INCLUDE_DIRS}
)

# Add project symbols (macros)
target_compile_definitions(${CMAKE_PROJECT_NAME} PRIVATE
    # Add user defined symbols
)

# Remove wrong libob.a library dependency when using cpp files
list(REMOVE_ITEM CMAKE_C_IMPLICIT_LINK_LIBRARIES ob)

# Add linked libraries
target_link_libraries(${CMAKE_PROJECT_NAME}
    stm32cubemx

    # Add user defined libraries
)

# Post-build: Generate .hex and .bin files for flashing
add_custom_command(TARGET ${CMAKE_PROJECT_NAME} POST_BUILD
    COMMAND ${CMAKE_OBJCOPY} -O ihex $<TARGET_FILE:${CMAKE_PROJECT_NAME}> ${CMAKE_CURRENT_BINARY_DIR}/${CMAKE_PROJECT_NAME}.hex
    COMMAND ${CMAKE_OBJCOPY} -O binary $<TARGET_FILE:${CMAKE_PROJECT_NAME}> ${CMAKE_CURRENT_BINARY_DIR}/${CMAKE_PROJECT_NAME}.bin
    COMMENT "Generating ${CMAKE_PROJECT_NAME}.hex and ${CMAKE_PROJECT_NAME}.bin"
)

# Flash target: build + download to board via ST-LINK (select "flash" as build target in VS Code)
add_custom_target(flash
    COMMAND powershell -NoProfile -ExecutionPolicy Bypass -File "${CMAKE_SOURCE_DIR}/flash.ps1"
    DEPENDS ${CMAKE_PROJECT_NAME}
    USES_TERMINAL
    COMMENT "Flashing ${CMAKE_PROJECT_NAME}.bin to STM32 board"
)

