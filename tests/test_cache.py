import unittest

from src.cache import Cache, CacheConfig


class CacheModelTests(unittest.TestCase):
    def test_direct_mapped_conflict_and_timing(self):
        cache = Cache(CacheConfig("direct", 32, 16, 1, "lru", 1, 20, 100))
        first = cache.access(0, "instruction")
        second = cache.access(32, "instruction")
        self.assertFalse(first.hit)
        self.assertFalse(second.hit)
        self.assertEqual(second.set_index, 0)
        self.assertEqual(second.evicted_block, 0)
        self.assertEqual(cache.stats.penalty_cycles, 240)

    def test_lru_updates_on_hit(self):
        cache = Cache(CacheConfig("set-associative", 64, 16, 2, "lru"))
        cache.access(0); cache.access(32); cache.access(0); result = cache.access(64)
        self.assertEqual(result.evicted_block, 2)

    def test_fifo_does_not_update_on_hit(self):
        cache = Cache(CacheConfig("set-associative", 64, 16, 2, "fifo"))
        cache.access(0); cache.access(32); cache.access(0); result = cache.access(64)
        self.assertEqual(result.evicted_block, 0)

    def test_fully_associative_uses_one_set(self):
        cache = Cache(CacheConfig("fully-associative", 64, 16, 1))
        self.assertEqual(cache.config.set_count, 1)
        self.assertEqual(cache.access(48).set_index, 0)

    def test_invalid_geometry(self):
        with self.assertRaises(ValueError): CacheConfig("set-associative", 64, 16, 3)
        with self.assertRaises(ValueError): CacheConfig("direct", 64, 16, 2)


if __name__ == "__main__":
    unittest.main()
