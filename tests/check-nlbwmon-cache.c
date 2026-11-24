/* SPDX-License-Identifier: ISC */
#include <assert.h>
#include <stdio.h>
#include "mac-miss-cache.h"

static struct mac_miss_cache cache;

int main(void)
{
	uint8_t a[MAC_MISS_KEY_SIZE] = { 4, 192, 168, 88, 10 };
	uint8_t b[MAC_MISS_KEY_SIZE] = { 4, 192, 168, 88, 11 };
	unsigned int i;
	assert(sizeof(cache) <= 256 * 1024);
	assert(!mac_miss_hit(&cache, a, 100));
	mac_miss_mark(&cache, a, 100);
	for (i = 0; i < 20000; i++)
		assert(mac_miss_hit(&cache, a, 101));
	assert(!mac_miss_hit(&cache, b, 101));
	assert(!mac_miss_hit(&cache, a, 100 + MAC_MISS_TTL_MS));
	mac_miss_mark(&cache, b, 200);
	mac_miss_forget(&cache, a);
	assert(mac_miss_hit(&cache, b, 201));
	mac_miss_forget(&cache, b);
	assert(!mac_miss_hit(&cache, b, 201));
	mac_miss_mark(&cache, a, 0);
	assert(!mac_miss_hit(&cache, a, 0));
	/* Distinct keys and hash eviction never produce another host's hit. */
	for (i = 0; i < 100000; i++) {
		memcpy(a + 8, &i, sizeof(i));
		mac_miss_mark(&cache, a, 300);
		assert(mac_miss_hit(&cache, a, 301));
		assert(!mac_miss_hit(&cache, b, 301));
	}
	puts("MAC failure cache: repeated misses, expiry, recovery and bounded eviction passed");
	return 0;
}
