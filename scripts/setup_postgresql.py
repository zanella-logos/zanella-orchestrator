"""Provision local databases and store the app secret in Windows Credential Manager."""

import argparse
from getpass import getpass
import secrets

import keyring
import psycopg
from psycopg import sql

from rpa_control_center.credentials import POSTGRES_SERVICE, POSTGRES_USERNAME


HOST = "localhost"
PORT = 5432
DATABASES = ("rpa_control_center", "rpa_control_center_test")


def provision(admin_password: str, repair: bool = False) -> None:
    if not admin_password:
        raise ValueError("Senha não informada.")

    app_password = secrets.token_urlsafe(32)
    with psycopg.connect(
        host=HOST,
        port=PORT,
        dbname="postgres",
        user="postgres",
        password=admin_password,
        autocommit=True,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (POSTGRES_USERNAME,))
            role_exists = cursor.fetchone() is not None
            if role_exists and not repair:
                raise RuntimeError(
                    "O usuário rcc_app já existe. Execute novamente com --repair "
                    "para gerar e armazenar uma nova senha do aplicativo."
                )

            role_command = "ALTER ROLE {} LOGIN PASSWORD {}" if role_exists else "CREATE ROLE {} LOGIN PASSWORD {}"
            cursor.execute(
                sql.SQL(role_command).format(
                    sql.Identifier(POSTGRES_USERNAME),
                    sql.Literal(app_password),
                )
            )
            created_role = not role_exists
            created_databases: list[str] = []
            try:
                for database in DATABASES:
                    cursor.execute(
                        "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s",
                        (database,),
                    )
                    existing = cursor.fetchone()
                    if existing:
                        if existing[0] != POSTGRES_USERNAME:
                            raise RuntimeError(
                                f"O banco {database} já existe, mas pertence a {existing[0]}."
                            )
                        continue
                    cursor.execute(
                        sql.SQL("CREATE DATABASE {} OWNER {}").format(
                            sql.Identifier(database),
                            sql.Identifier(POSTGRES_USERNAME),
                        )
                    )
                    created_databases.append(database)
            except BaseException:
                for database in created_databases:
                    cursor.execute(
                        sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                            sql.Identifier(database)
                        )
                    )
                if created_role:
                    cursor.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(POSTGRES_USERNAME)))
                raise

    keyring.set_password(POSTGRES_SERVICE, POSTGRES_USERNAME, app_password)


def run_console(repair: bool) -> None:
    print("Configuração local do PostgreSQL para o Zanella Orchestrator")
    print("A senha administrativa não será exibida nem armazenada pelo script.")
    admin_password = getpass("Senha do usuário postgres: ")
    provision(admin_password, repair=repair)
    print("Banco operacional e banco de testes criados.")
    print("Credencial rcc_app armazenada no Windows Credential Manager.")


def run_gui(repair: bool) -> None:
    import tkinter as tk
    from tkinter import messagebox, simpledialog

    root = tk.Tk()
    root.withdraw()
    try:
        password = simpledialog.askstring(
            "Zanella Orchestrator",
            "Digite a senha do usuário postgres:\n\nEla não será armazenada.",
            show="*",
            parent=root,
        )
        if password is None:
            return
        provision(password, repair=repair)
        messagebox.showinfo(
            "Zanella Orchestrator",
            "Banco operacional e banco de testes criados.\n"
            "A credencial rcc_app foi salva no cofre do Windows.",
            parent=root,
        )
    except Exception as error:
        messagebox.showerror("Zanella Orchestrator", str(error), parent=root)
        raise
    finally:
        root.destroy()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--repair", action="store_true")
    arguments = parser.parse_args()
    run_gui(arguments.repair) if arguments.gui else run_console(arguments.repair)


if __name__ == "__main__":
    main()
