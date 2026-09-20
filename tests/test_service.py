import pytest
from pathlib import Path
import sys
from sqlalchemy import text
from rpa_control_center.models import Base, Robot, Run
from rpa_control_center.service import add_robot, list_runs, list_robots
from rpa_control_center.store import make_engine
from sqlalchemy.orm import Session

def test_filters_and_pagination(tmp_path: Path):
    db_path = tmp_path / "test.db"
    db_engine = make_engine("sqlite:///" + db_path.as_posix())
    Base.metadata.create_all(db_engine)

    # 1. Create robots
    robot_ids = []
    for i in range(5):
        robot_id = add_robot(
            db_engine,
            name=f"Robot Test {i}",
            script="fake.py",
            interpreter="python",
            cwd=".",
            arguments=[],
            timeout=10,
            executor_type="powershell" if i == 4 else "python",
        )
        robot_ids.append(robot_id)

    # 2. Add some runs
    with Session(db_engine) as session, session.begin():
        for i, r_id in enumerate(robot_ids):
            run1 = Run(robot_id=r_id, configuration={"name": f"Robot Test {i}"}, state="queued", business_result="not_reported")
            run2 = Run(robot_id=r_id, configuration={"name": f"Robot Test {i}"}, state="failed", business_result="business_error")
            run3 = Run(robot_id=r_id, configuration={"name": f"Robot Test {i}"}, state="completed", business_result="success")
            session.add_all([run1, run2, run3])

    # 3. Test list_robots search
    robots = list_robots(db_engine, search="Test 2")
    assert len(robots) == 1
    assert robots[0].name == "Robot Test 2"

    robots = list_robots(db_engine, search="powershell")
    assert len(robots) == 1
    assert robots[0].name == "Robot Test 4"

    # 4. Test list_runs state filter
    runs, count = list_runs(db_engine, state="queued")
    assert count == 5
    assert all(r.state == "queued" for r in runs)

    # 5. Test list_runs business filter
    runs, count = list_runs(db_engine, business_result="business_error")
    assert count == 5
    assert all(r.business_result == "business_error" for r in runs)

    # 6. Test list_runs search (Join)
    runs, count = list_runs(db_engine, search="Test 3")
    assert count == 3

    # 7. Test Pagination
    runs, count = list_runs(db_engine, limit=2, offset=0)
    assert count == 15
    assert len(runs) == 2

    runs_page_2, count2 = list_runs(db_engine, limit=2, offset=2)
    assert len(runs_page_2) == 2
    assert runs[0].id != runs_page_2[0].id

    db_engine.dispose()
