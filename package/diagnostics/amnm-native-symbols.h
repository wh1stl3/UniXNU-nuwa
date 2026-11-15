/* Intermediate-only native renderer symbol bindings; not a device candidate. */
extern unsigned char vinfo[], vm_page_pages[], vm_page_free_count[], max_mem[];
static unsigned char amnm_local_panic_text[2048];
#define VINFO ((unsigned long)vinfo)
#define PANIC_TEXT ((unsigned long)amnm_local_panic_text)
#define PAGE_TOTAL ((unsigned long)vm_page_pages)
#define PAGE_FREE ((unsigned long)vm_page_free_count)
#define MAX_MEM ((unsigned long)max_mem)
