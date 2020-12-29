/* SPDX-License-Identifier: MIT */

#include <gtest/gtest.h>

extern "C" {
#include "dummy.h"
}

TEST(testrunner, test_add) {
    int a = dummyFunction(1, 1);
    ASSERT_EQ(2, a);
}

int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
