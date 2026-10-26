/*
	Simple logger for returning messages across the DLL interface
	*/
#include <string>

#pragma once

/* Anim.cpp needs these */
#define wxLogMessage niflydll::LogWriteMf
#define wxLogWarning niflydll::LogWriteWf
#define wxLogError niflydll::LogWriteEf

namespace niflydll {

	void LogInit();

	void LogWrite(std::string msg);
	void LogWriteMf(std::string msg, ...);
	void LogWriteWf(std::string msg, ...);
	void LogWriteEf(std::string msg, ...);

	int LogGetLen();

	int LogGet(char* buf, int len);

	/* Copy a string out to a caller's buffer of len bytes. Never writes past the buffer:
	   copies at most len-1 characters and always NUL-terminates when len > 0 (buf may be
	   null or len 0 to just ask the length). Returns the FULL length of the source, so a
	   caller can learn the size it needs with a small buffer and call again ("Len-then-fill"). */
	int copy_out(char* buf, int len, const std::string& s);
	int copy_out(char* buf, int len, const char* s);

}