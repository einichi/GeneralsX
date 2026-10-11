// GeneralsX @bugfix Codex 11/10/2026 Convert script-format failures into recoverable match errors.
#pragma once
#include "Common/GameDataError.h"
#include "Common/Errors.h"
#include "Common/GameMemory.h"
#include "Common/DataChunk.h"
#include "GameLogic/Scripts.h"

inline void parseRequiredScriptFile(DataChunkInput& file, void* userData, const AsciiString& path)
{
    Bool parsed = FALSE;
    try {
        parsed = file.parse(userData);
    } catch (ErrorCode error) {
        if (error != ERROR_CORRUPT_FILE_FORMAT) throw;
    }
    if (!parsed) {
        ScriptList* scripts[MAX_PLAYER_COUNT];
        const Int count = ScriptList::getReadScripts(scripts);
        for (Int i = 0; i < count; ++i) deleteInstance(scripts[i]);
        throw GameDataError(path, "Unable to parse required match scripts. Verify the complete game installation.");
    }
}
