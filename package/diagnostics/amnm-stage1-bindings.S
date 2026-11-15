/* UNUSABLE stage-one native-layout placeholders, never a final binding. */
.text
.p2align 2
.globl _amnm_input_continue, _amnm_store_continue, _amnm_branch_zero
.globl _amnm_branch_nonzero, _amnm_entry_continue, _amnm_precall_continue
.globl _amnm_precall_return, _amnm_reader_binding, _amnm_return_binding
_amnm_input_continue:
_amnm_store_continue:
_amnm_branch_zero:
_amnm_branch_nonzero:
_amnm_entry_continue:
_amnm_precall_continue:
_amnm_precall_return:
_amnm_reader_binding:
_amnm_return_binding:
    brk #0
.data
.p2align 3
.globl _amnm_flag_binding
_amnm_flag_binding:
    .quad 0
