/* SPDX-License-Identifier: MIT */

/* clang-format off */
#include <memory>
#include "gtest/gtest.h"
#include "gmock/gmock.h"
using namespace ::testing;
using ::testing::Return;
/* clang-format on */

/* clang-format off */
extern "C" {
#include "add.h"
#include "dummy.h"
}
/* clang-format on */

class DummyMock {
  public:
    virtual ~DummyMock() {}
    // MOCK_METHOD(int, dummyFunction, (int a, int b), ());
    MOCK_METHOD2(dummyFunction, int(int a, int b));
};

class AddTestWithMockedDummy : public ::testing::Test {
  public:
    AddTestWithMockedDummy() { _dummyMock.reset(new ::testing::NiceMock<DummyMock>()); }

    ~AddTestWithMockedDummy() { _dummyMock.reset(); }
    virtual void SetUp() {}
    virtual void TearDown() {}

    static std::unique_ptr<DummyMock> _dummyMock;
};

std::unique_ptr<DummyMock> AddTestWithMockedDummy::_dummyMock;

int dummyFunction(int a, int b) {
    return AddTestWithMockedDummy::_dummyMock->dummyFunction(a, b);
}

TEST_F(AddTestWithMockedDummy, test_add) {
    EXPECT_CALL(*_dummyMock, dummyFunction(1, 1)).WillOnce(Return(2));
    EXPECT_EQ(2, add(1, 1));
}

int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    return RUN_ALL_TESTS();
}
