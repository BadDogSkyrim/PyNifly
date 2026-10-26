/*
	Simple logger for returning messages across the DLL interface
	*/
#include <string>
#include <vector>
#include <cstdarg>
#include <algorithm>
#include "Logger.hpp"

namespace niflydll {
	static std::vector<std::string> messageLog;

	void LogInit() {
		messageLog.clear();
	}

	void LogWrite(std::string msg) {
		messageLog.push_back(msg);
	}

	void LogWriteMf(std::string fmt, ...)
	{
		char buf[500];
		va_list args;
		va_start(args, fmt);
		std::string msg = "Info: " + fmt;
		vsnprintf(buf, 500, msg.c_str(), args);
		messageLog.push_back(buf);
		va_end(args);
	}

	void LogWriteWf(std::string fmt, ...)
	{
		char buf[500];
		va_list args;
		va_start(args, fmt);
		std::string msg = "WARNING: " + fmt;
		vsnprintf(buf, 500, msg.c_str(), args);
		messageLog.push_back(buf);
		va_end(args);
	}

	void LogWriteEf(std::string fmt, ...)
	{
		char buf[500];
		va_list args;
		va_start(args, fmt);
		std::string msg = "ERROR: " + fmt;
		vsnprintf(buf, 500, msg.c_str(), args);
		messageLog.push_back(buf);
		va_end(args);
	}

	int LogGetLen() {
		int len = 0;
		for (std::string s : messageLog) {
			len += int(s.size() + 1);
		}
		return len;
	}

	int LogGet(char* buf, int len) {
		std::string outStr;
		for (std::string s : messageLog) {
			outStr += s + '\n';
		};
		return copy_out(buf, len, outStr);
	}

	int copy_out(char* buf, int len, const std::string& s) {
		if (buf && len > 0) {
			size_t n = std::min(size_t(len) - 1, s.size());
			s.copy(buf, n, 0);
			buf[n] = '\0';
		}
		return int(s.size());
	}

	int copy_out(char* buf, int len, const char* s) {
		return copy_out(buf, len, std::string(s ? s : ""));
	}

}