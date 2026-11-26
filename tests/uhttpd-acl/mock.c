#include <libubus.h>
#include <libubox/uloop.h>
#include <libubox/blobmsg.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
static struct ubus_context *bus;
struct late_reply { struct uloop_timeout timer; struct ubus_request_data req; };
static void late_cb(struct uloop_timeout *t)
{
 struct late_reply *l=container_of(t, struct late_reply, timer);
 struct blob_buf b={}; blob_buf_init(&b,0); blobmsg_add_u8(&b,"access",1);
 ubus_send_reply(bus,&l->req,b.head);
 ubus_complete_deferred_request(bus,&l->req,0); blob_buf_free(&b); free(l);
}
static int access_cb(struct ubus_context *ctx, struct ubus_object *obj,
 struct ubus_request_data *req, const char *method, struct blob_attr *msg)
{
 struct ubus_request_data deferred;
 if (access("/tmp/uhttpd-lab/late", F_OK) == 0) {
  struct late_reply *l=calloc(1,sizeof(*l));
  if (!l) return UBUS_STATUS_UNKNOWN_ERROR;
  ubus_defer_request(ctx,req,&l->req); l->timer.cb=late_cb;
  uloop_timeout_set(&l->timer,6500); return 0;
 }
 struct blob_buf b = {};
 if (access("/tmp/uhttpd-lab/hang", F_OK) == 0) {
  ubus_defer_request(ctx, req, &deferred);
  fprintf(stderr, "deferred access request\n");
  return 0;
 }
 blob_buf_init(&b, 0);
 blobmsg_add_u8(&b, "access", access("/tmp/uhttpd-lab/deny", F_OK) != 0);
 ubus_send_reply(ctx, req, b.head);
 blob_buf_free(&b);
 return 0;
}
static int ping_cb(struct ubus_context *ctx, struct ubus_object *obj,
 struct ubus_request_data *req, const char *method, struct blob_attr *msg)
{
 struct blob_buf b = {};
 FILE *f=fopen("/tmp/uhttpd-lab/invocations","a"); if (f) { fputs("ping\n",f); fclose(f); }
 blob_buf_init(&b, 0); blobmsg_add_string(&b, "reply", "pong");
 ubus_notify(ctx,obj,"test",b.head,-1);
 ubus_send_reply(ctx, req, b.head); blob_buf_free(&b); return 0;
}
static const struct ubus_method session_methods[] = { UBUS_METHOD_NOARG("access", access_cb) };
static const struct ubus_method test_methods[] = { UBUS_METHOD_NOARG("ping", ping_cb) };
static struct ubus_object_type session_type = UBUS_OBJECT_TYPE("session", session_methods);
static struct ubus_object_type test_type = UBUS_OBJECT_TYPE("test", test_methods);
static struct ubus_object session_obj = { .name="session", .type=&session_type, .methods=session_methods, .n_methods=1 };
static struct ubus_object test_obj = { .name="test", .type=&test_type, .methods=test_methods, .n_methods=1 };
int main(int argc, char **argv)
{
 if (argc != 2) return 2;
 uloop_init(); bus=ubus_connect(argv[1]); if (!bus) return 3;
 ubus_add_uloop(bus);
 if (ubus_add_object(bus,&session_obj) || ubus_add_object(bus,&test_obj)) return 4;
 uloop_run(); ubus_free(bus); uloop_done(); return 0;
}
