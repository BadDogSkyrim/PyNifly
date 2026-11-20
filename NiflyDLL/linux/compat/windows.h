// The little of <windows.h> NiflyDLL uses, for the Linux build: FindProjectRoot asks for the path of the library holding
// one of its own functions, which dladdr answers.
#pragma once
#include <dlfcn.h>
#include <cstring>
#include <climits>
typedef void* HMODULE;
typedef const char* LPCSTR;
typedef char* LPSTR;
typedef int BOOL;
typedef unsigned long DWORD;
#ifndef MAX_PATH
#define MAX_PATH PATH_MAX
#endif
#define GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS 0x4
#define GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT 0x2
// The "handle" is the file name dladdr gives for the address: the library's own path.
inline BOOL GetModuleHandleExA(DWORD, LPCSTR address, HMODULE* module) {
    Dl_info info{};
    if (!dladdr(reinterpret_cast<const void*>(address), &info) || !info.dli_fname) return 0;
    *module = const_cast<char*>(info.dli_fname);
    return 1;
}
inline DWORD GetModuleFileNameA(HMODULE module, LPSTR buffer, DWORD size) {
    if (!module || !size) return 0;
    std::strncpy(buffer, static_cast<const char*>(module), size - 1);
    buffer[size - 1] = '\0';
    return static_cast<DWORD>(std::strlen(buffer));
}
