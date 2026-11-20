// Included first in the Linux build: MSVC's export marker means nothing to GCC, where every symbol is exported by default.
#pragma once
#define __declspec(x)
