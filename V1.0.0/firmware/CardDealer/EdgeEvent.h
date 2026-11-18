#pragma once
#include <stdint.h>
// Kept in a header so Arduino's automatic function prototypes know this type.
struct ExitEdge {uint32_t us;bool blocked;};
