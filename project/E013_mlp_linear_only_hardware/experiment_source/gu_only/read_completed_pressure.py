#!/usr/bin/env python3
"""Read completed native report sections; launch no EDA and modify no design."""
import datetime
import hashlib
import json
from pathlib import Path


def main():
    base = Path("project/hardware/vivado/reports/m006_slr_AT001_physopt_slr")
    files = {name: base / name for name in
             ("slice_sites.tsv", "congestion.rpt", "crossing_global.rpt")}
    board = []
    for line in files["slice_sites.tsv"].read_text().splitlines()[1:]:
        slr, scope, capacity, occupied = line.split("\t")
        if scope == "board":
            board.append(dict(slr=slr, capacity_slice_sites=int(capacity),
                              primitive_occupied_slice_sites=int(occupied)))
    assert len(board) == 3
    fanout = []
    for line in files["crossing_global.rpt"].read_text().splitlines():
        cells = [s.strip() for s in line.split("|")[1:-1]]
        if len(cells) == 6 and cells[0].isdigit() and int(cells[0]) >= 4000:
            fanout.append(dict(fanout=int(cells[0]), driver_type=cells[1],
                               loads_by_slr_raw=cells[2:5], net=cells[5]))
    assert any(r["fanout"] == 6185 and r["net"].endswith(
        "u_down_scheduler/u_projection_repack/input_fire") for r in fanout)
    congestion = []
    for line in files["congestion.rpt"].read_text().splitlines():
        cells = [s.strip() for s in line.split("|")[1:-1]]
        if len(cells) == 16 and cells[:3] == ["South", "Global", "6"]:
            congestion.append(dict(direction=cells[0], type=cells[1],
                                   level=int(cells[2]), window=cells[3],
                                   combined_luts=cells[4], uram=cells[11],
                                   cell_names_raw=cells[-1]))
    assert len(congestion) == 1
    output = dict(
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source_dcp_stage="saved_physopt_postPlace_pre_route",
        dcp_sha256="5c5238bac4b4560ce05d070dc15e91ca09bec072884185149f18649c6f631d7e",
        scope="completed_native_report_sections_while_remaining_sections_still_running",
        source_files=[dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                      for p in files.values()],
        slice_sites=board,
        native_cross_slr_fanout_at_least_4000=fanout,
        representative_congestion_row=congestion,
        limits=[
            "Not the failed-route live design: no routed DCP was exported",
            "Cell Names percentages describe this window, not expected savings",
            "Present structures do not predict post-removal placement or route success",
            "Parent and child scopes and occupied sites cannot be summed",
        ],
    )
    output["extractor_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    target = Path(__file__).with_name("native_pressure_support.json")
    target.write_text(json.dumps(output, indent=2) + "\n")
    print(f"{target}: {len(board)} SLR rows, {len(fanout)} fanout rows, "
          f"{len(congestion)} representative congestion row")


if __name__ == "__main__":
    main()
