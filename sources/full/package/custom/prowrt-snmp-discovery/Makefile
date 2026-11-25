include $(TOPDIR)/rules.mk
PKG_NAME:=prowrt-snmp-discovery
PKG_VERSION:=1.0.0
PKG_RELEASE:=1
PKG_LICENSE:=MIT
include $(INCLUDE_DIR)/package.mk

define Package/prowrt-snmp-discovery
  SECTION:=net
  CATEGORY:=Network
  TITLE:=Read-only routed SNMP inventory for QuickStart
  DEPENDS:=+lua +luci-lib-jsonc +luci-lib-nixio +luci-compat +snmp-utils-ssl
  PKGARCH:=all
endef

define Package/prowrt-snmp-discovery/conffiles
/etc/config/lingjing_snmp
endef

define Build/Compile
endef

define Package/prowrt-snmp-discovery/install
	$(CP) ./root/. $(1)/
endef

$(eval $(call BuildPackage,prowrt-snmp-discovery))
