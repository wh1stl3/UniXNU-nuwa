// SPDX-License-Identifier: BSD-2-Clause-Patent
/*
 * nuwa r12a: minimal replacement for the two verified-block helpers that r12 took from
 * the official VirtioMmioBlock component.  r12 linked that whole component into the
 * native kernel, which added an OSMetaClass constructor to the kernel's own
 * __mod_init_func list; the r12 device run stopped before the video console, so this
 * variant keeps the SystemOS mount but removes the component entirely.
 *
 * What is kept and what is not:
 *   * native_verified_block_volume_device() still resolves the volume by IOMedia UUID
 *     and still requires the window's own signed-volume check through ShengUfs'
 *     native_ufs_block_authenticates() (the strong part).
 *   * native_verified_block_root_authorized() reports acceptance, because the r11
 *     bring-up skips root authentication (8796-nuwa-root-auth-skip) and records the
 *     errno separately; the value is only shown on the boot page, it does not gate.
 *
 * No IOService subclass, no personality, no __mod_init_func: nothing here runs before
 * load_init_program().
 *
 * Provenance: the lookup follows UniXNU/drivers/VirtioMmioBlock/NativeVirtioBlock.cpp
 * native_verified_block_volume_device() (BSD-2-Clause-Patent), reduced to the parts the
 * nuwa bring-up uses (the virtio transport, verification snapshot and personality are
 * not included).
 */
#include <IOKit/IOLib.h>
#include <IOKit/IOService.h>
#include <IOKit/IORegistryEntry.h>
#include <IOKit/IOBSD.h>
#include <libkern/c++/OSDictionary.h>
#include <libkern/c++/OSIterator.h>
#include <libkern/c++/OSNumber.h>
#include <libkern/c++/OSString.h>
#include <sys/types.h>
#include <sys/param.h>

extern "C" int native_ufs_block_authenticates(IOService *, const char *, uint8_t *);

extern "C" {
volatile uint32_t native_verified_block_volume_lookups = 0;
volatile uint32_t native_verified_block_volume_matches = 0;
volatile uint32_t native_verified_block_root_authorized_calls = 0;
volatile uint32_t native_verified_block_root_authorized_result = 1;
}

extern "C" int
native_verified_block_root_authorized(dev_t device)
{
	(void)device;
	native_verified_block_root_authorized_calls = native_verified_block_root_authorized_calls + 1;
	/* r11 accepted the root through 8796-nuwa-root-auth-skip; the recorded errno is
	 * nuwa_root_auth_error.  Report 1 (accepted) and keep the count for the screen. */
	native_verified_block_root_authorized_result = 1;
	return 1;
}

extern "C" int
native_verified_block_volume_device(const char *uuid, dev_t *device, char *path, size_t size)
{
	if (!uuid || !device || !path || size < 6 || strlen(uuid) != 36) {
		return 0;
	}
	*device = NODEV;
	path[0] = 0;
	native_verified_block_volume_lookups = native_verified_block_volume_lookups + 1;
	native_verified_block_volume_matches = 0;

	OSDictionary *matching = IOService::serviceMatching("IOMedia");
	OSDictionary *properties = OSDictionary::withCapacity(1);
	OSString *wanted = OSString::withCString(uuid);
	if (!matching || !properties || !wanted) {
		OSSafeReleaseNULL(wanted);
		OSSafeReleaseNULL(properties);
		OSSafeReleaseNULL(matching);
		return 0;
	}
	bool ready = properties->setObject("UUID", wanted) && matching->setObject("IOPropertyMatch", properties);
	wanted->release();
	properties->release();
	OSIterator *iterator = ready ? IOService::getMatchingServices(matching) : nullptr;
	matching->release();
	if (!iterator) {
		return 0;
	}
	unsigned matches = 0;
	bool authenticated = false;
	dev_t candidate = NODEV;
	char candidatePath[64] = {};
	while (OSObject *object = iterator->getNextObject()) {
		IOService *media = OSDynamicCast(IOService, object);
		if (!media) {
			continue;
		}
		if (++matches != 1) {
			authenticated = false;
			break;
		}
		OSString *identity = OSDynamicCast(OSString, media->getProperty("UUID"));
		OSString *name = OSDynamicCast(OSString, media->getProperty(kIOBSDNameKey));
		OSNumber *mjr = OSDynamicCast(OSNumber, media->getProperty(kIOBSDMajorKey));
		OSNumber *mnr = OSDynamicCast(OSNumber, media->getProperty(kIOBSDMinorKey));
		if (!identity || strcmp(identity->getCStringNoCopy(), uuid) || !name || !mjr || !mnr ||
		    !name->getLength() || name->getLength() >= sizeof(candidatePath) - 6 ||
		    name->getLength() >= size - 6 ||
		    mjr->unsigned64BitValue() > 255 || mnr->unsigned64BitValue() > 0xffffff) {
			continue;
		}
		/* Walk up to the block service and require that window's own signed-volume
		 * check; native_ufs_block_authenticates() returns -1 for a non-UFS window. */
		bool window_ok = false;
		unsigned depth = 0;
		for (IOService *provider = media; provider && depth < 64; provider = provider->getProvider()) {
			++depth;
			int ufs = native_ufs_block_authenticates(provider, uuid, nullptr);
			if (ufs >= 0) {
				window_ok = (ufs == 1);
				break;
			}
		}
		if (!window_ok) {
			continue;
		}
		candidate = static_cast<dev_t>(makedev(mjr->unsigned32BitValue(), mnr->unsigned32BitValue()));
		snprintf(candidatePath, sizeof(candidatePath), "/dev/%s", name->getCStringNoCopy());
		authenticated = true;
	}
	iterator->release();
	native_verified_block_volume_matches = matches;
	if (!authenticated || matches != 1) {
		return 0;
	}
	*device = candidate;
	strlcpy(path, candidatePath, size);
	return 1;
}
