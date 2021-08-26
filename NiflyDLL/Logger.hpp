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

}