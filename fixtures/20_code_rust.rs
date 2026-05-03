// Syntax-heavy Rust fixture. Not intended to compile.
#![allow(dead_code, unused_variables)]
use std::{collections::HashMap, fmt::{self, Display}, future::Future, pin::Pin};

macro_rules! demo { ($($arg:tt)*) => { println!($($arg)*); }; }

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
enum Status { New, Running(u8), Done { ok: bool } }

trait Repository<K, V> where K: Eq + std::hash::Hash { fn get(&self, key: &K) -> Option<&V>; fn put(&mut self, key: K, value: V); }

struct Memory<K, V> { items: HashMap<K, V> }
impl<K: Eq + std::hash::Hash, V> Repository<K, V> for Memory<K, V> {
    fn get(&self, key: &K) -> Option<&V> { self.items.get(key) }
    fn put(&mut self, key: K, value: V) { self.items.insert(key, value); }
}

#[repr(C)] struct Point { x: i32, y: i32 }
impl Display for Point { fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result { write!(f, "{},{}", self.x, self.y) } }

async fn compute<'a, T>(input: &'a [T]) -> Result<usize, Box<dyn std::error::Error + Send + Sync>>
where T: Display + Clone + 'a {
    let count = input.iter().filter(|item| item.to_string().len() > 1).count();
    Ok(count)
}

fn pattern(value: Option<Result<Status, String>>) -> &'static str {
    match value {
        Some(Ok(Status::Running(n))) if n > 10 => "busy",
        Some(Ok(Status::Done { ok: true })) => "done",
        Some(Err(ref e)) if !e.is_empty() => "error",
        None | Some(_) => "other",
    }
}

unsafe extern "C" fn ffi(ptr: *const u8) -> usize { if ptr.is_null() { 0 } else { *ptr as usize } }

fn main() {
    let mut mem = Memory::<String, Vec<i32>> { items: HashMap::new() };
    mem.put("a".into(), vec![1, 2, 3]);
    let closure = |x: i32| -> i32 { x.saturating_add(1) };
    demo!("{} {:?}", closure(1), mem.get(&"a".to_string()));
}

// --- Additional representative Rust syntax coverage ---
pub mod extra_rust_syntax {
    pub const LIMIT: usize = 1_024;
    pub static NAME: &str = "fixture";
    pub struct TupleStruct(pub i32, pub i32);
    pub trait IteratorLike { type Item; fn next_item(&mut self) -> Option<Self::Item>; }
    pub fn parse<const N: usize>(input: &[u8; N]) -> Result<impl Iterator<Item = u8> + '_, std::str::Utf8Error> {
        let text = std::str::from_utf8(input)?;
        let raw = r#"raw string with "quotes" and # marks"#;
        let bytes = b"byte string";
        let mut sum = 0usize;
        for (index, byte) in input.iter().enumerate() { sum += index + *byte as usize; }
        if let Some(first) = input.first() { sum += *first as usize; }
        while let Some(ch) = text.chars().next() { let _ = ch; break; }
        let value = loop { break sum + (0..10).sum::<usize>(); };
        let (a, b) = (value, LIMIT);
        let move_closure = move |x: usize| x + a + b + raw.len() + bytes.len();
        Ok(input.iter().copied().map(move_closure).map(|x| x as u8))
    }
    pub async fn async_block() -> Result<(), Box<dyn std::error::Error>> {
        let future = async { Ok::<_, std::io::Error>(()) };
        future.await?;
        Ok(())
    }
}
