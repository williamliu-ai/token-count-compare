// Syntax-heavy TypeScript fixture. Not intended to compile.
type Id = string | number;
type AwaitedReturn<T extends (...args: any) => any> = Awaited<ReturnType<T>>;
type ReadonlyDeep<T> = { readonly [K in keyof T]: T[K] extends object ? ReadonlyDeep<T[K]> : T[K] };

interface Entity<TMeta extends Record<string, unknown> = {}> { id: Id; meta?: TMeta; }
interface Repository<T extends Entity> { get(id: T["id"]): Promise<T | undefined>; save(...items: readonly T[]): void; }

const enum Status { New = "new", Done = "done" }
abstract class Base<T extends Entity> implements Repository<T> {
  protected cache = new Map<Id, T>();
  abstract transform<U extends T>(item: U): U & { status: Status };
  async get(id: Id): Promise<T | undefined> { return this.cache.get(id); }
  save(...items: readonly T[]): void { for (const item of items) this.cache.set(item.id, item); }
}

class Users extends Base<Entity<{ role: "admin" | "user" }>> {
  #private = 1;
  transform<U extends Entity>(item: U) { return { ...item, status: Status.New } as U & { status: Status }; }
  overload(value: string): string;
  overload(value: number): number;
  overload(value: string | number) { return value; }
}

function isEntity(value: unknown): value is Entity { return !!value && typeof value === "object" && "id" in value; }
function assertNever(x: never): never { throw new Error(String(x)); }

const tuple = ["x", 1, true] as const satisfies readonly [string, number, boolean];
const maybe: Partial<Record<Status, Entity>> = { [Status.New]: { id: "1" } };
const result = tuple.map((value, index) => ({ value, index }))?.[0] ?? null;

export async function main<T extends Entity>(repo: Repository<T>, input: unknown) {
  if (isEntity(input)) repo.save(input as T);
  for await (const item of asyncGenerator()) console.log(item);
  return result;
}

async function* asyncGenerator(): AsyncGenerator<string, void, unknown> { yield "demo"; }

// --- Additional representative TypeScript syntax coverage ---
/**
 * JSDoc fixture with @template T and @param input - representative comments.
 */
type ElementOf<T> = T extends readonly (infer U)[] ? U : never;
type Route = `/api/${"users" | "projects"}/${string}`;
type NamedTuple = [id: Id, label?: string, ...flags: boolean[]];
type Dict<T> = { [key: string]: T };

enum RegularStatus { Idle, Busy = "busy" }
type Event =
  | { kind: "created"; id: string; payload?: Dict<unknown> }
  | { kind: "deleted"; id: string; hard?: boolean };

namespace AmbientFixture { export declare const version: string; }
function sealed(_: Function) {}
@sealed
class DecoratedTs {
  get value(): number { return 1_000n as unknown as number; }
  set value(v: number) { this.#assign(v!); }
  #assign(_v: number) {}
}

function handleEvent(event: Event): string {
  switch (event.kind) {
    case "created": return event.payload?.name as string ?? "created";
    case "deleted": return event.hard ? "hard-delete" : "soft-delete";
    default: return assertNever(event);
  }
}
const tuple2: NamedTuple = ["id", "label", true, false];
const route: Route = `/api/users/${tuple2[0]}`;
