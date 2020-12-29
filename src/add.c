/* SPDX-License-Identifier: MIT */

#include "add.h"
#include "dummy.h"

int add(int a, int b) {
    int result = 0;
    result = dummyFunction(a, b);
    return result;
}
