// Syntax-heavy Go fixture. Not intended to compile.
package main

import (
    "context"
    "errors"
    "fmt"
    "io"
    "sync"
)

type Number interface{ ~int | ~int64 | ~float64 }
type Status string
const ( New Status = "new"; Done Status = "done" )

type Entity[T any] struct { ID string; Value T; Tags []string }
type Repository[T any] interface { Get(context.Context, string) (T, error); Put(context.Context, T) error }

type Memory[T Number] struct { mu sync.RWMutex; items map[string]Entity[T] }

func NewMemory[T Number]() *Memory[T] { return &Memory[T]{items: map[string]Entity[T]{}} }
func (m *Memory[T]) Get(ctx context.Context, id string) (Entity[T], error) {
    m.mu.RLock(); defer m.mu.RUnlock()
    if v, ok := m.items[id]; ok { return v, nil }
    return Entity[T]{}, fmt.Errorf("missing %q: %w", id, io.EOF)
}
func (m *Memory[T]) Put(ctx context.Context, item Entity[T]) error { m.mu.Lock(); defer m.mu.Unlock(); m.items[item.ID] = item; return nil }

func classify[T Number](value T) string {
    switch any(value).(type) {
    case int, int64: return "integer"
    case float64: return "float"
    default: return "unknown"
    }
}

func stream[T Number](ctx context.Context, in <-chan Entity[T]) <-chan string {
    out := make(chan string)
    go func() {
        defer close(out)
        for {
            select {
            case <-ctx.Done(): return
            case item, ok := <-in:
                if !ok { return }
                out <- fmt.Sprintf("%s=%v", item.ID, item.Value)
            }
        }
    }()
    return out
}

func main() {
    defer func(){ if r := recover(); r != nil { fmt.Println(r) } }()
    repo := NewMemory[int](); _ = repo.Put(context.Background(), Entity[int]{ID:"a", Value:1, Tags: []string{"x"}})
    if _, err := repo.Get(context.Background(), "b"); errors.Is(err, io.EOF) { fmt.Println("missing") }
}

// ExtraGo documents representative Go syntax, including tags and iota.
//go:build fixture

type Kind int
const (
    KindUnknown Kind = iota
    KindAlpha
    KindBeta
)

type Embedded struct { io.Reader }
type Tagged struct {
    ID   string `json:"id" db:"id"`
    Name string `json:"name,omitempty"`
}

func moreGoSyntax(input any) (result string, err error) {
Label:
    for k, v := range map[string]int{"hex": 0xFF, "bin": 0b1010, "dec": 1_000} {
        _ = k
        if v, ok := input.(int); ok && v > 0 { result = fmt.Sprintf(`raw string %d`, v); break Label }
        switch v { case 1: fallthrough; default: continue }
    }
    var embedded = struct { Embedded; Tagged }{Tagged: Tagged{ID: "x"}}
    _ = embedded
    return
}
