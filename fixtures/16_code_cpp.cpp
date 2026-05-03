// Syntax-heavy C++ fixture. Not intended to compile.
#include <algorithm>
#include <concepts>
#include <coroutine>
#include <iostream>
#include <map>
#include <memory>
#include <optional>
#include <ranges>
#include <string>
#include <variant>
#include <vector>

#define DEMO(x) do { std::cout << #x << "=" << (x) << '\n'; } while (false)

template <typename T>
concept Numeric = requires(T a, T b) { { a + b } -> std::convertible_to<T>; };

namespace example {
enum class Status : unsigned { New, Running, Done };
struct Point { int x; int y; auto operator<=>(const Point&) const = default; };
using Value = std::variant<int, double, std::string>;

template <Numeric T>
class Box final {
    std::unique_ptr<T> value_;
public:
    explicit Box(T value) : value_(std::make_unique<T>(value)) {}
    Box(Box&&) noexcept = default;
    Box& operator=(Box&&) noexcept = default;
    ~Box() = default;
    T get() const noexcept { return *value_; }
    friend std::ostream& operator<<(std::ostream& os, const Box& b) { return os << b.get(); }
};

template <class... Ts> struct overloaded : Ts... { using Ts::operator()...; };
template <class... Ts> overloaded(Ts...) -> overloaded<Ts...>;

constexpr auto lambda = []<typename T>(T&& item) noexcept(noexcept(T{item})) { return std::forward<T>(item); };

std::optional<std::string> describe(Value v) {
    return std::visit(overloaded{
        [](int i) { return std::optional{std::to_string(i)}; },
        [](double d) { return std::optional{std::format("{}", d)}; },
        [](const std::string& s) -> std::optional<std::string> { return s.empty() ? std::nullopt : std::optional{s}; }
    }, v);
}
}

int main() {
    std::vector<int> nums{1, 2, 3, 4};
    for (auto n : nums | std::views::filter([](int x){ return x % 2 == 0; })) DEMO(n);
    try { throw std::runtime_error("fixture"); }
    catch (const std::exception& e) { std::cerr << e.what(); }
    return 0;
}

// --- Additional representative C++ syntax coverage ---
[[nodiscard]] static constexpr auto more_cpp_syntax() -> int {
    int binary = 0b1010'0101;
    unsigned long long mask = 0xffULL;
    const char* raw = R"cpp(raw string with {braces}, "quotes", and \slashes)cpp";
    const char8_t* utf8 = u8"snowman \u2603";
    auto point = example::Point{.x = 1, .y = 2};
    auto [x, y] = point;
    if constexpr (sizeof(void*) >= 8) { mask <<= 1; }
    if (auto value = static_cast<int>(mask); value > 0) { value ^= x | y; }
    switch (binary & 0b11) { case 0: break; case 1: [[fallthrough]]; default: binary += 1; }
    decltype(binary) copy = reinterpret_cast<std::uintptr_t>(nullptr);
    return binary + static_cast<int>(copy);
}

struct CoroutineFixture {
    struct promise_type {
        CoroutineFixture get_return_object() { return {}; }
        std::suspend_never initial_suspend() noexcept { return {}; }
        std::suspend_never final_suspend() noexcept { return {}; }
        void return_void() noexcept {}
        void unhandled_exception() {}
    };
};
CoroutineFixture coroutine_fixture() { co_await std::suspend_never{}; co_return; }
struct Base { virtual ~Base() = default; virtual void run() = 0; };
struct Derived final : Base { void run() override {} };
