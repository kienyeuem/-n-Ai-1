"""
Cấp / thu hồi quyền admin cho user.

Cách dùng:
    python make_admin.py                           # Liệt kê tất cả user + role
    python make_admin.py promote kientran          # Đặt kientran thành admin
    python make_admin.py demote  kientran          # Hạ kientran về user thường
    python make_admin.py delete  kientran          # Xoá hẳn user
    python make_admin.py reset-password kientran   # Đặt lại mật khẩu (cho random)
"""
import json, sys, os, hashlib, secrets

USERS_FILE = os.path.join(os.path.dirname(__file__), 'data', 'users.json')


def _hash(p):
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', p.encode(), salt.encode(), 120_000)
    return f'pbkdf2_sha256${salt}${h.hex()}'


def load():
    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save(items):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def cmd_list():
    items = load()
    print(f'\nDanh sách user ({len(items)}):')
    print('-' * 70)
    print(f'{"USERNAME":<20} {"ROLE":<8} {"LOCKED":<8} {"EMAIL"}')
    print('-' * 70)
    for u in items:
        role = u.get('role', 'user')
        lock = 'YES' if u.get('locked') else 'no'
        marker = '👑 ' if role == 'admin' else '   '
        print(f'{marker}{u["username"]:<17} {role:<8} {lock:<8} {u.get("email","")}')
    print()


def find(items, username):
    for u in items:
        if u['username'].lower() == username.lower():
            return u
    return None


def cmd_promote(username):
    items = load()
    u = find(items, username)
    if not u:
        print(f'❌ Không tìm thấy user "{username}"')
        sys.exit(1)
    u['role'] = 'admin'
    save(items)
    print(f'✅ Đã cấp quyền admin cho "{u["username"]}" ({u.get("email","")})')


def cmd_demote(username):
    items = load()
    u = find(items, username)
    if not u:
        print(f'❌ Không tìm thấy user "{username}"'); sys.exit(1)
    u['role'] = 'user'
    save(items)
    print(f'✅ Đã hạ "{u["username"]}" về role user')


def cmd_delete(username):
    items = load()
    u = find(items, username)
    if not u:
        print(f'❌ Không tìm thấy user "{username}"'); sys.exit(1)
    confirm = input(f'Xoá hẳn "{u["username"]}" ({u.get("email","")})? [y/N] ').strip().lower()
    if confirm != 'y':
        print('Đã huỷ.'); return
    items = [x for x in items if x['username'].lower() != username.lower()]
    save(items)
    print(f'✅ Đã xoá "{username}"')


def cmd_reset_password(username):
    items = load()
    u = find(items, username)
    if not u:
        print(f'❌ Không tìm thấy user "{username}"'); sys.exit(1)
    new_pw = secrets.token_urlsafe(8)
    u['password'] = _hash(new_pw)
    save(items)
    print(f'✅ Đã reset mật khẩu cho "{u["username"]}"')
    print(f'   Mật khẩu mới: {new_pw}  (lưu lại trước khi thoát!)')


if __name__ == '__main__':
    if len(sys.argv) == 1:
        cmd_list(); sys.exit(0)
    cmd = sys.argv[1].lower()
    if cmd in ('list', 'ls'):
        cmd_list()
    elif cmd == 'promote' and len(sys.argv) == 3:
        cmd_promote(sys.argv[2])
    elif cmd == 'demote' and len(sys.argv) == 3:
        cmd_demote(sys.argv[2])
    elif cmd == 'delete' and len(sys.argv) == 3:
        cmd_delete(sys.argv[2])
    elif cmd in ('reset-password', 'reset') and len(sys.argv) == 3:
        cmd_reset_password(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)
