/*
	Simple logger for returning messages across the DLL interface
	*/
#include <string>

#pragma once

/* Anim.cpp needs these */
#define wxLogMessage LogWritef
#define wxLogWarning LogWritef
#define wxLogError LogWritef


void LogInit();

void LogWrite(std::string msg);
void LogWritef(std::string msg, ...);

int LogGetLen();

void LogGet(char* buf, int len);

