import re

def parse_room_code(room_code):
    room_str = str(room_code).strip()
    room_str = re.sub(r'\D', '', room_str)
    building = room_str[0]
    room_number = room_str[1:]
    return {
        'building': building,
        'room_number': room_number
    }

def parse_room_code_alternative(room_code):
    room_str = str(room_code).strip()
    if '-' in room_str:
        parts = [p.strip() for p in room_str.split('-')]
        if len(parts) == 3:
            return {
                'building': parts[0],
                'entrance': parts[1],
                'room_number': parts[2]
            }
        elif len(parts) == 2:
            return {
                'building': parts[0],
                'room_number': parts[1]
            }
    if '.' in room_str:
        parts = room_str.split('.', 1)
        if len(parts) == 2:
            return {
                'building': parts[0].strip(),
                'room_number': parts[1].strip()
            }
    return parse_room_code(room_str)

