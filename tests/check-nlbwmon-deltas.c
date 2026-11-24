/* SPDX-License-Identifier: ISC */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <errno.h>
struct record { uint64_t count, in_bytes, out_bytes, in_pkts, out_pkts; };
static void *gdbh;
static struct record saved;
static int exists, calls;
static int database_insert(void *db, struct record *r)
{
    (void)db; exists=1;calls++;
    saved.count+=r->count;saved.in_bytes+=r->in_bytes;saved.out_bytes+=r->out_bytes;
    return 0;
}
int database_update(void *db, struct record *r)
{
    if (!exists) return -ENOENT;
    return database_insert(db, r);
}
#include "accounting.c"
int main(void)
{
    struct record refresh={.out_bytes=1052};
    database_insert_immediately(&refresh);
    assert(exists && saved.count==0 && saved.out_bytes==1052);
    struct record event={.count=1};
    database_insert_immediately(&event);
    assert(saved.count==1 && saved.out_bytes==1052);
    struct record empty={0};
    database_insert_immediately(&empty);
    assert(calls==2);
    struct record reply={.in_bytes=1052};
    database_insert_immediately(&reply);
    assert(saved.in_bytes==1052 && saved.out_bytes==1052 && saved.count==1);
    puts("Observed deltas before NEW are retained without adding connections or idle rows");
    return 0;
}
