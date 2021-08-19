/*
	Simple logger for returning messages across the DLL interface
	*/
#include <string>

#pragma once

/* Anim.cpp needs these */
#define wxLogMessage niflydll::LogWritef
#define wxLogWarning niflydll::LogWritef
#define wxLogError niflydll::LogWritef

namespace niflydll {

	void LogInit();

	void LogWrite(std::string msg);
	void LogWritef(std::string msg, ...);

	int LogGetLen();

	void LogGet(char* buf, int len);

}