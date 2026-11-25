// Shared host lock is held by Provider; the window is its validated Data window.
struct RetainedWritePort {
  NuwaData::Evidence writePageLocked(unsigned lun, NuwaData::Window window,
                                     uint64_t lba, uint32_t blocks, const uint8_t *src) {
    using NuwaData::Evidence;
    if (!src || blocks != 1 || !window.contains(lun, combined_state.block, lba, blocks) ||
        !RootReadSession::span(combined_state, lun, lba, blocks) ||
        !retainedSlot.writeInFlight() || !retainedHostUsableLocked()) return Evidence::Unowned;
    combined_state.readLba = lba;
    combined_state.readBlocks = 1;
    // issue() checks the retained domain/ownership before prepare and again
    // before ringing DB0. prepare encodes then publishes the CPU payload.
    const auto end = CombinedRead::issue(combined_hardware, combined_state,
                                        CombinedRead::Command::WriteFua, src);
    auto evidence = retainedCompletion(end, true);
    if (evidence == Evidence::FullFua && combined_state.returned != NuwaData::Block)
      evidence = Evidence::Unowned;
    // Provider records completion on the same lock; never clear/quiesce DMA.
    if (evidence != Evidence::FullFua) blockRetainedHostLocked();
    return evidence;
  }
};
