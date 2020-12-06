/* SPDX-License-Identifier: MIT */

#include <gtest/gtest.h>

extern "C" {
#include "super.h"
}

TEST(testrunner, test_add) {
    int a = add(1,1);
    ASSERT_EQ(a, 2);
}


int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
