// Included inside CombinedRead after senseValid() and senseCode().
static End response(State &s, const volatile uint8_t *r) {
  const unsigned type = s.command == Command::Query || s.command == Command::QueryDesc ? 0x36 : 0x21;
  const unsigned dl = unsigned(r[10]) << 8 | r[11];
  if (r[0] != type || r[2] != lun(s.command) || r[3] != s.tag ||
      r[8] || dl > 480) return End::Response;
  if (s.command == Command::QueryDesc) {
    s.queryResult = r[6];
    switch (NuwaUfsDesc::response(s.desc, r, dl)) {
      case NuwaUfsDesc::Reply::Good: return End::Success;
      case NuwaUfsDesc::Reply::Rejected: return End::QueryError;
      case NuwaUfsDesc::Reply::Unowned: return End::Response;
    }
  }
  if (s.command == Command::Query) {
    s.queryResult = r[6];
    if (dl || r[1] || r[5] != 1 || r[6] || r[7] || r[12] != 3 ||
        r[13] != 2 || r[14] || r[15] || r[16] || r[17] || r[18] || r[19])
      return End::Response;
    s.power = be32(r + 20);
    return End::Success;
  }

  s.status = r[7];
  s.residual = be32(r + 12);
  s.sense = 0;
  const unsigned expected = s.command == Command::Read ? s.block * s.readBlocks :
                                                         length(s.command, s.block);
  // Only the supported command response form: no overflow, unknown flags,
  // UPIU error response, or contradictory/oversized residual.
  if (r[6] || (r[1] & ~0x20U) || bool(r[1] & 0x20) != bool(s.residual) ||
      s.residual > expected) return End::Response;

  switch (s.status) {
    case 0x00: // MODE SENSE payload length is checked by its bounded parser.
      if (dl || (s.command == Command::Sense ? expected - s.residual < 8 :
                 s.command != Command::ModeSense && s.residual))
        return End::Response;
      return End::Success;
    case 0x02: { // CHECK CONDITION: require well-formed autosense.
      if (dl < 2) return End::Response;
      const unsigned sl = unsigned(r[32]) << 8 | r[33];
      if (sl != dl - 2 || !senseValid(r + 34, sl)) return End::Response;
      s.sense = senseCode(r + 34, sl);
      return End::Scsi;
    }
    default:
      // Not supported: CONDITION MET (04), BUSY (08), INTERMEDIATE (10),
      // INTERMEDIATE-CONDITION MET (14), RESERVATION CONFLICT (18), COMMAND
      // TERMINATED (22), TASK SET FULL (28), ACA ACTIVE (30), TASK ABORTED
      // (40), and all other/reserved values (including ff).
      return End::Response;
  }
}
