"""Independently recompute AT007 first native MLP group from byte addresses."""
import hashlib, json, re
from pathlib import Path
root = Path(__file__).resolve().parents[6]
log = root / 'project/hardware/vivado/reports/m002_R002_AT007_dedicated_real_frontends_diagnostic/xsim.log'
if not log.exists():
    matches = sorted((root / 'project/hardware/vivado/reports').glob('m002_R002_AT007*/xsim.log'))
    if len(matches) != 1:
        raise SystemExit(f'Need exactly one AT007 xsim.log, got {matches}')
    log = matches[0]
text = log.read_text()
m = re.search(r'MLP_DIAGNOSTIC[^\n]*got=([0-9a-fA-FxX]+) expected=([0-9a-fA-FxX]+) meta=([0-9a-fA-FxX]+) expected_meta=([0-9a-fA-FxX]+)', text)
if not m:
    raise SystemExit('Missing AT007 full group diagnostic')
got_hex, expected_hex, meta_hex, expected_meta_hex = m.groups()
words = []
for stream in range(2):
    for beat in range(2):
        for word in range(16):
            address = 0x00100000 + 0x04000000 + stream * 0x01000000 + beat * 64 + word * 4
            words.append((address ^ 0x5ac31f07 ^ (word * 0x01010101)) & 0xffffffff)
expected = b''.join(word.to_bytes(4, 'little') for word in words)
got = int(got_hex, 16).to_bytes(256, 'little')
assert got == expected, 'actual native MLP payload differs from independent Python address model'
assert set(expected_hex.lower()) == {'x'}, 'AT007 SV oracle was not entirely X'
assert meta_hex.lower() == expected_meta_hex.lower(), 'AT007 metadata differs'
report = dict(log=str(log), log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
              scope='AT007 native MLP first group only; independent CPU oracle crosscheck',
              group_bytes=len(expected), full_payload_equal=True,
              verilog_expected_all_x=True, metadata_equal=True,
              expected_payload_sha256=hashlib.sha256(expected).hexdigest(),
              first_word=f'{words[0]:08x}', last_word=f'{words[-1]:08x}')
output = Path(__file__).with_name('AT007_independent_oracle_crosscheck.json')
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
