/*
	Simple logger for returning messages across the DLL interface
	*/
#include <string>
#include <vector>
#include <cstdarg>

static std::vector<std::string> messageLog;

void LogInit() {
	messageLog.clear();
}

void LogWrite(std::string msg) {
	messageLog.push_back(msg);
}

void LogWritef(std::string fmt, ...)
{
	char buf[500];
	va_list args;
	va_start(args, fmt);
	vsnprintf(buf, 500, fmt.c_str(), args);
	va_end(args);
}

int LogGetLen() {
	int len = 0;
	for (std::string s : messageLog) {
		len += int(s.size() + 1);
	}
	return len;
}

void LogGet(char* buf, int len) {
	std::string outStr;
	for (std::string s : messageLog) {
		outStr += s + '\n';
	};
	strcpy_s(buf, len - 1, outStr.c_str());
	buf[len - 1] = '\0';
}

