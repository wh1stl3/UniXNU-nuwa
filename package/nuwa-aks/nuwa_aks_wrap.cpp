/*
 * r31: the two things the vendored AppleKeyStoreState component must not carry itself.
 *
 * 1. The class registration bracket.  The component declares its classes with
 *    OSDefineMetaClassAndStructors, so the metaclasses are created by the file's static
 *    initializer.  Calling that initializer bare leaves className a raw char* and the class
 *    unregistered - the r26/r27 crash in OSMetaClass::getClassName().  The bracket is
 *    OSMetaClass::preModLoad("__kernel__") -> __GLOBAL__sub_I_NativeKeyStoreEvents.cpp ->
 *    OSMetaClass::postModLoad(), the same shape r29 uses for NativeRamBlock; "__kernel__" is
 *    kOSKextKernelIdentifier, the kext OSRuntimeInitializeCPP() records the kernel's own
 *    classes under.
 *
 * 2. The explicit instance creation.  native_keyevents_allocate() is the component's own entry
 *    point (the last line of the file).  The instance is attached to IOResources and started
 *    after bsd_init()/bsd_autoconf(), i.e. from the Data mount, where the registry is
 *    connected and registerService() has a parent - the r27 timing, not the r26 one.
 */
#include <IOKit/IOService.h>

extern "C" void nuwa_aks_ctor(void) __asm__("__GLOBAL__sub_I_NativeKeyStoreEvents.cpp");
extern "C" IOService *native_keyevents_allocate(void);
extern "C" int native_aks_state_enabled(void);

extern "C" int
native_keyevents_register_class(void)
{
	void *handle = OSMetaClass::preModLoad("__kernel__");
	OSReturn result;

	if (!handle) {
		IOLog("AppleKeyStore: register: preModLoad failed\n");
		return 0;
	}
	nuwa_aks_ctor();
	result = OSMetaClass::postModLoad(handle);
	IOLog("AppleKeyStore: register: postModLoad=%d\n", (int)result);
	return result == kOSReturnSuccess ? 1 : 0;
}

extern "C" int
native_keyevents_start_service(void)
{
	IOService *resources;
	IOService *service;

	if (!native_aks_state_enabled()) {
		return 0;
	}
	resources = IOService::getResourceService();
	if (resources == NULL) {
		IOLog("AppleKeyStore: create reject 1: no IOResources service\n");
		return -1;
	}
	service = native_keyevents_allocate();
	if (service == NULL) {
		IOLog("AppleKeyStore: create reject 2: allocation failed\n");
		return -2;
	}
	if (!service->init()) {
		IOLog("AppleKeyStore: create reject 3: init failed\n");
		service->release();
		return -3;
	}
	if (!service->attach(resources)) {
		IOLog("AppleKeyStore: create reject 4: attach(IOResources) failed\n");
		service->release();
		return -4;
	}
	if (!service->start(resources)) {
		IOLog("AppleKeyStore: create reject 5: start failed\n");
		service->detach(resources);
		service->release();
		return -5;
	}
	IOLog("AppleKeyStore: created: attached to IOResources and started\n");
	return 1;
}
