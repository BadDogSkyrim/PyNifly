# Linux build of NiflyDLL as libNiflyDLL.so: the sources NiflyDLL.vcxproj compiles, against BadDogSkyrim's nifly.
# nifly is found where the Visual Studio project expects it, beside the PyNifly checkout as Nifly (..\..\Nifly from
# NiflyDLL), else in NiflyDLL/external/nifly; -DNIFLY_DIR=<path> names another. See LINUX.md.
cmake_minimum_required(VERSION 3.16)
project(NiflyDLL_Linux LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

set(DLL ${CMAKE_CURRENT_SOURCE_DIR}/..)
if(NOT NIFLY_DIR)
    if(EXISTS ${DLL}/../../Nifly/CMakeLists.txt)
        set(NIFLY_DIR ${DLL}/../../Nifly)
    else()
        set(NIFLY_DIR ${DLL}/external/nifly)
    endif()
endif()
if(NOT EXISTS ${NIFLY_DIR}/CMakeLists.txt)
    message(FATAL_ERROR "nifly not found at ${NIFLY_DIR}: clone https://github.com/BadDogSkyrim/nifly there, or pass -DNIFLY_DIR=<path>")
endif()
add_subdirectory(${NIFLY_DIR} nifly)

add_library(NiflyDLL SHARED ${DLL}/Anim.cpp ${DLL}/Logger.cpp ${DLL}/NiflyFunctions.cpp ${DLL}/NiflyWrapper.cpp)
# compat/ first: its windows.h stands in for the one Windows call NiflyDLL makes.
target_include_directories(NiflyDLL PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/compat ${DLL} ${NIFLY_DIR}/include ${NIFLY_DIR}/external)
target_compile_definitions(NiflyDLL PRIVATE NIFLYDLL_EXPORTS)
target_compile_options(NiflyDLL PRIVATE -include ${CMAKE_CURRENT_SOURCE_DIR}/compat/prelude.h)
target_link_libraries(NiflyDLL PRIVATE nifly ${CMAKE_DL_LIBS})
