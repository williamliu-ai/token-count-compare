// Syntax-heavy Swift fixture. Not intended to compile.
import Foundation

@propertyWrapper struct Clamped<Value: Comparable> {
    private var value: Value
    let range: ClosedRange<Value>
    var wrappedValue: Value { get { value } set { value = min(max(newValue, range.lowerBound), range.upperBound) } }
    init(wrappedValue: Value, _ range: ClosedRange<Value>) { self.range = range; self.value = wrappedValue }
}

protocol Repository<Key, Value> { associatedtype Key: Hashable; associatedtype Value; subscript(key: Key) -> Value? { get set } }
enum Status: String, Codable, CaseIterable { case new, running, done }

struct User: Codable, Hashable, CustomStringConvertible {
    let id: UUID
    var name: String
    @Clamped(0...150) var age: Int = 0
    var description: String { "\(name)<\(id)>" }
}

actor Memory<K: Hashable, V>: Repository {
    private var items: [K: V] = [:]
    subscript(key: K) -> V? { get { items[key] } set { items[key] = newValue } }
    func values(where predicate: (V) async throws -> Bool) async rethrows -> [V] {
        var output: [V] = []
        for value in items.values where try await predicate(value) { output.append(value) }
        return output
    }
}

extension Optional where Wrapped == String { var nonEmpty: String? { flatMap { $0.isEmpty ? nil : $0 } } }

func describe(_ value: Any) -> String {
    switch value {
    case let user as User where user.age >= 18: return "adult \(user)"
    case let status as Status: return status.rawValue
    case let tuple as (Int, String): return "\(tuple.0):\(tuple.1)"
    case is Never: fatalError()
    default: return "unknown"
    }
}

@main struct App {
    static func main() async throws {
        let memory = Memory<UUID, User>()
        let user = User(id: UUID(), name: "Ada", age: 42)
        await memory[user.id] = user
        async let adults = memory.values { $0.age > 17 }
        print(try await adults.map(\.description).joined(separator: ","))
    }
}

// --- Additional representative Swift syntax coverage ---
@available(macOS 14, *)
enum ExtraSwiftSyntax<Value> {
    case loaded(Value)
    case failed(any Error)
    case empty
}

protocol ExtraService { func load() async throws -> some Sequence<String> }
func mutate(_ value: inout Int, transform: @escaping @autoclosure () -> Int) { value += transform() }

final class MoreSwiftSyntax {
    lazy var cached: [String] = []
    static func ~= (pattern: String, value: String) -> Bool { value.contains(pattern) }
    func run(input: String?) async -> String {
        defer { print("done") }
        guard let input, !input.isEmpty else { return "empty" }
        if let number = Int(input) { return "number \(number)" }
        do {
            var count = 0
            mutate(&count, transform: input.count)
            let closure: () -> String = { [weak self] in self?.cached.first ?? input }
            switch ExtraSwiftSyntax.loaded(closure()) {
            case .loaded(let value) where value ~= "x": return value
            case .failed(let error as NSError): throw error
            case .empty, .failed: return "none"
            }
        } catch {
            return error.localizedDescription
        }
    }
}

@resultBuilder enum LinesBuilder { static func buildBlock(_ parts: String...) -> [String] { parts } }
