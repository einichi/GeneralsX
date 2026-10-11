// GeneralsX @bugfix Codex 11/10/2026 Report incomplete match data without starting broken gameplay.
#pragma once
#include <stdexcept>
#include <string>
#include "Common/AsciiString.h"

class GameDataError : public std::runtime_error
{
public:
    GameDataError(const AsciiString& resource, const char* reason)
        : std::runtime_error(std::string(reason) + "\n" + resource.str()) {}
};
