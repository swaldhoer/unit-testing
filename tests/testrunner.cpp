/* SPDX-License-Identifier: MIT */

#include <gtest/gtest.h>

TEST(module_name, dummy_test) {
    ASSERT_EQ(1 + 1, 2);
}

int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
