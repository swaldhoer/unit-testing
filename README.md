# Simple Unit Testing

## Getting Started

1. Get the repository

   ```sh
   $ git clone https://github.com/swaldhoer/unit-testing.git
   $ cd unit-testing
   ```

1. Configure, build and test the project

   ```sh
   $ ./waf.sh configure --googletest-bootstrap
   $ ./waf.sh build_bin
   $ ./waf.sh build_test
   ```

1. Run clang-format on the project

   ```sh
   $ ./waf.sh clang-format --cf-arg -i
   ```
