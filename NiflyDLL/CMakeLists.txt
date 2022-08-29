cmake_minimum_required(VERSION 3.16...3.23)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_INTERPROCEDURAL_OPTIMIZATION OFF)
set(CMAKE_INSTALL_PREFIX "${CMAKE_SOURCE_DIR}/publish")
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
set_property(GLOBAL PROPERTY USE_FOLDERS ON)

project(NiflyDLL LANGUAGES CXX)

# --------------------------------------------------
# Add submodules
add_subdirectory(external/nifly)

# --------------------------------------------------
# Create interface libs
add_library(nifly_dll_warnings INTERFACE)
if(MSVC)
    target_compile_options(nifly_dll_warnings INTERFACE /W3 /WX /permissive-)
else()
    target_compile_options(nifly_dll_warnings INTERFACE -Wall -Wextra -pedantic -Werror)
endif()

add_library(nifly_dll_definitions INTERFACE)
target_compile_definitions(nifly_dll_definitions INTERFACE NIFLYDLL_EXPORTS)
if(MSVC)
    target_compile_definitions(nifly_dll_definitions INTERFACE
        WIN32_LEAN_AND_MEAN
        NOMINMAX)
endif()

add_library(nifly_dll_dependencies INTERFACE)
target_link_libraries(nifly_dll_dependencies INTERFACE
    nifly)

add_library(nifly_dll_pch INTERFACE)
target_precompile_headers(nifly_dll_pch INTERFACE
    <string>
    <string_view>
    <array>
    <vector>
    <deque>
    <map>
    <unordered_map>
    <set>
    <unordered_set>
    <fstream>
    <regex>
    <filesystem>
    <variant>
    <functional>
    <algorithm>
    <codecvt>
    <iomanip>
    <locale>
    <mutex>
    include/framework.hpp)


# --------------------------------------------------
# Create engine lib
file(GLOB_RECURSE nifly_dll_sources CONFIGURE_DEPENDS "src/*.cpp")
file(GLOB_RECURSE nifly_dll_headers CONFIGURE_DEPENDS "include/*.hpp")
add_library(nifly_dll SHARED ${nifly_dll_sources} ${nifly_dll_headers})
set_target_properties(nifly_dll PROPERTIES OUTPUT_NAME NiflyDLL)
target_link_libraries(nifly_dll PRIVATE
    nifly_dll_warnings
    nifly_dll_definitions
    nifly_dll_dependencies
    nifly_dll_pch)
target_include_directories(nifly_dll PRIVATE "include")


# --------------------------------------------------
# Merge files from source and include in the IDE
function(group_files sources)
    foreach(FILE ${sources})
        # Get the directory of the source file
        get_filename_component(PARENT_DIR "${FILE}" DIRECTORY)

        # Remove common directory prefix to make the group
        string(REPLACE "${CMAKE_CURRENT_SOURCE_DIR}" "" GROUP "${PARENT_DIR}")

        # Make sure we are using windows slashes
        string(REPLACE "/" "\\" GROUP "${GROUP}")

        # Strip the root parts for each possible component
        if("${FILE}" MATCHES "include/.*")
            string(SUBSTRING ${GROUP} 8 -1 GROUP)
        elseif("${FILE}" MATCHES "src/.*")
            string(SUBSTRING ${GROUP} 4 -1 GROUP)
        endif()

        # Do the grouping
        source_group("${GROUP}" FILES "${FILE}")
    endforeach()
endfunction()
group_files("${nifly_dll_sources};${nifly_dll_headers}")


# --------------------------------------------------
# Install app
install(TARGETS
    nifly_dll
    RUNTIME
    DESTINATION .)

