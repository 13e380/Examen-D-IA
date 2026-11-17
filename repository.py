"""Persistance SQLite des plaintes, de leur historique et de leurs pièces jointes."""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

import engine as eng


class ComplaintRepository:
    """Dépôt SQLite des plaintes (incidents), événements et pièces jointes."""
    def __init__(self, database_path: Optional[str] = None) -> None:
        """Ouvre (ou crée) la base. Chemin : argument, puis variable CIVITAS_DB_PATH, puis .data/civitas.sqlite3."""
        default_path = Path(__file__).resolve().parent / ".data" / "civitas.sqlite3"
        self.path = Path(database_path or os.getenv("CIVITAS_DB_PATH", str(default_path)))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Connexion SQLite validée en fin de bloc et annulée en cas d'erreur."""
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        """Crée les tables si elles n'existent pas."""
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS complaints (
                    id INTEGER PRIMARY KEY,
                    rule_id TEXT NOT NULL,
                    district TEXT NOT NULL,
                    description TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    role TEXT NOT NULL,
                    victims INTEGER NOT NULL,
                    factors_json TEXT NOT NULL,
                    score REAL NOT NULL,
                    priority TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    trace_json TEXT NOT NULL,
                    assignments_json TEXT NOT NULL,
                    eta INTEGER,
                    transcript TEXT,
                    image_name TEXT,
                    latitude REAL,
                    longitude REAL,
                    resolved_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_complaints_status_created
                    ON complaints(status, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_complaints_priority
                    ON complaints(priority, score DESC);

                CREATE TABLE IF NOT EXISTS complaint_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    complaint_id INTEGER NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
                    action TEXT NOT NULL,
                    details TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_complaint_events_complaint
                    ON complaint_events(complaint_id, created_at DESC);

                CREATE TABLE IF NOT EXISTS complaint_attachments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    complaint_id INTEGER NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
                    filename TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    data BLOB NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _serialize(incident: eng.Incident) -> tuple:
        """Convertit un incident en ligne SQL (les listes et dictionnaires en JSON)."""
        return (
            incident.id,
            incident.rule_id,
            incident.district,
            incident.description,
            incident.channel,
            incident.role,
            int(incident.victims),
            json.dumps(incident.factors, ensure_ascii=False),
            incident.score,
            incident.priority,
            incident.reason,
            incident.created_at.isoformat(),
            incident.seq,
            incident.status,
            json.dumps(incident.trace, ensure_ascii=False),
            json.dumps(incident.assignments, ensure_ascii=False),
            incident.eta,
            incident.transcript,
            incident.image_name,
            incident.latitude,
            incident.longitude,
            incident.resolved_at.isoformat() if incident.resolved_at else None,
        )

    @staticmethod
    def _to_incident(row: sqlite3.Row) -> eng.Incident:
        """Reconstruit un incident à partir d'une ligne SQL."""
        return eng.Incident(
            id=row["id"],
            rule_id=row["rule_id"],
            district=row["district"],
            description=row["description"],
            channel=row["channel"],
            role=row["role"],
            victims=bool(row["victims"]),
            factors=json.loads(row["factors_json"]),
            score=row["score"],
            priority=row["priority"],
            reason=row["reason"],
            created_at=datetime.fromisoformat(row["created_at"]),
            seq=row["seq"],
            status=row["status"],
            trace=[tuple(item) for item in json.loads(row["trace_json"])],
            assignments=json.loads(row["assignments_json"]),
            eta=row["eta"],
            transcript=row["transcript"],
            image_name=row["image_name"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
        )

    def save_complaint(
        self,
        incident: eng.Incident,
        action: str,
        details: str = "",
        attachments: tuple[tuple[str, str, bytes], ...] = (),
    ) -> None:
        """Enregistre l'incident, ajoute un événement à son historique et stocke ses pièces jointes."""
        values = self._serialize(incident)
        placeholders = ", ".join("?" for _ in values)
        updates = ", ".join(
            f"{column} = excluded.{column}"
            for column in (
                "rule_id", "district", "description", "channel", "role", "victims",
                "factors_json", "score", "priority", "reason", "created_at", "seq",
                "status", "trace_json", "assignments_json", "eta", "transcript",
                "image_name", "latitude", "longitude", "resolved_at",
            )
        )
        with self._connection() as connection:
            connection.execute(
                f"""
                INSERT INTO complaints (
                    id, rule_id, district, description, channel, role, victims,
                    factors_json, score, priority, reason, created_at, seq, status,
                    trace_json, assignments_json, eta, transcript, image_name,
                    latitude, longitude, resolved_at
                ) VALUES ({placeholders})
                ON CONFLICT(id) DO UPDATE SET {updates}
                """,
                values,
            )
            if attachments:
                images_size = sum(len(data) for _, content_type, data in attachments if content_type.startswith("image/"))
                audio_size = sum(len(data) for _, content_type, data in attachments if content_type.startswith("audio/"))
                if images_size > 20 * 1024 * 1024:
                    raise ValueError("Le total des photos dépasse 20 Mo.")
                if audio_size > 50 * 1024 * 1024:
                    raise ValueError("Le total des fichiers audio dépasse 50 Mo.")
                connection.execute(
                    "DELETE FROM complaint_attachments WHERE complaint_id = ?", (incident.id,)
                )
                connection.executemany(
                    """
                    INSERT INTO complaint_attachments
                        (complaint_id, filename, content_type, data, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (incident.id, filename, content_type, data, datetime.now().isoformat())
                        for filename, content_type, data in attachments
                    ],
                )
            connection.execute(
                """
                INSERT INTO complaint_events (complaint_id, action, details, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (incident.id, action, details, datetime.now().isoformat()),
            )

    def list_complaints(self, include_resolved: bool = True) -> list[eng.Incident]:
        """Liste les plaintes, résolues comprises par défaut."""
        query = "SELECT * FROM complaints"
        if not include_resolved:
            query += " WHERE status != ?"
            parameters = (eng.STATUS_RESOLVED,)
        else:
            parameters = ()
        query += " ORDER BY CASE priority WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 "
        query += "WHEN 'P3' THEN 3 ELSE 4 END, score DESC, seq DESC"
        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._to_incident(row) for row in rows]

    def get_complaint(self, complaint_id: int) -> Optional[eng.Incident]:
        """Retourne une plainte par son numéro, ou None."""
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM complaints WHERE id = ?", (complaint_id,)
            ).fetchone()
        return self._to_incident(row) if row else None

    def get_attachments(self, complaint_id: int) -> tuple[tuple[str, str, bytes], ...]:
        """Pièces jointes d'une plainte : (nom de fichier, type MIME, contenu)."""
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT filename, content_type, data FROM complaint_attachments
                WHERE complaint_id = ? ORDER BY id
                """,
                (complaint_id,),
            ).fetchall()
        return tuple(
            (row["filename"], row["content_type"], bytes(row["data"]))
            for row in rows
        )

    def get_events(self, complaint_id: int) -> list[dict[str, str]]:
        """Historique horodaté des actions sur une plainte."""
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT action, details, created_at FROM complaint_events
                WHERE complaint_id = ? ORDER BY id DESC
                """,
                (complaint_id,),
            ).fetchall()
        return [dict(row) for row in rows]
