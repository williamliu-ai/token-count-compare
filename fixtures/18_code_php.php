<?php
// Syntax-heavy PHP fixture. Not intended to run.
declare(strict_types=1);

namespace Example\Syntax;

use Attribute;
use Closure;
use Countable;
use Generator;
use Stringable;
use Throwable;

#[Attribute(Attribute::TARGET_CLASS | Attribute::TARGET_METHOD)]
class Demo { public function __construct(public string $name = 'demo') {} }

enum Status: string { case New = 'new'; case Done = 'done'; }

trait Logger { public function log(string $msg): void { echo $msg, PHP_EOL; } }

interface Repository { public function find(int|string $id): ?object; }

#[Demo('syntax')]
final readonly class User implements Stringable
{
    public function __construct(public int $id, public string $name, public ?Status $status = null) {}
    public function __toString(): string { return "{$this->id}:{$this->name}"; }
}

class Service implements Repository, Countable
{
    use Logger;
    /** @var array<int|string, User> */ private array $items = [];
    public function __construct(private Closure $factory) {}
    public function find(int|string $id): ?object { return $this->items[$id] ?? null; }
    public function count(): int { return count($this->items); }
    public function add(User ...$users): static { foreach ($users as $u) $this->items[$u->id] = $u; return $this; }
    public function stream(): Generator { yield from $this->items; }
}

try {
    $service = new Service(fn(array $data): User => new User(...$data));
    $match = match ($service->count()) { 0 => 'empty', 1, 2 => 'few', default => 'many' };
    foreach ($service->stream() as $key => $value) { $service->log($key . ':' . $value?->name); }
} catch (Throwable $e) {
    throw new \RuntimeException(previous: $e, message: 'wrapped');
} finally {
    $nullable = null;
}

/**
 * Additional PHPDoc block.
 * @template T of object
 * @param array<int, string> $items
 * @return never
 */
function more_php_syntax(array $items): never
{
    $doc = <<<HTML
<div class="fixture">{$items[0]}</div>
HTML;
    $raw = <<<'TXT'
nowdoc $notInterpolated with backslashes \ and quotes "
TXT;
    [$first, $second] = $items + [null, null];
    $items['count'] ??= count($items);
    $cmp = $items['count'] <=> 10;
    $label = $cmp > 0 ? 'many' : ($cmp === 0 ?: 'few');
    global $GLOBAL_FIXTURE;
    $GLOBAL_FIXTURE = $label;
    $anon = new class($doc, $raw) extends \ArrayObject {
        public function __construct(private string $doc, private string $raw) { parent::__construct([]); }
        public function __invoke(): string { return static::class . parent::class . $this->doc . $this->raw; }
    };
    throw new \LogicException($anon());
}

abstract class MorePhpBase { abstract public function run(\Countable&\Stringable $value): (\Countable&\Stringable)|false; }
