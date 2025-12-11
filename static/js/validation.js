const Validation = {
    availableRooms: [],
    roomsLoaded: false,

    loadAvailableRooms() {
        if (this.roomsLoaded) {
            return Promise.resolve();
        }

        return $.ajax({
            url: '/api/rooms/list',
            method: 'GET',
            success: (data) => {
                if (data.success && data.rooms) {
                    this.availableRooms = data.rooms;
                    this.roomsLoaded = true;
                }
            },
            error: (xhr) => {
            }
        });
    },

    validateRoom() {
        const building = $('#building').val().trim();
        const entrance = $('#entrance').val().trim();
        const roomNumber = $('#room_number').val().trim();


        $('.room-validation-error').remove();

        if (!building && !entrance && !roomNumber) {
            return true;
        }

        if (!this.roomsLoaded) {
            this.loadAvailableRooms().then(() => this.validateRoom());
            return false;
        }

        const roomExists = this.availableRooms.some(room => {
            const roomBuilding = (room.building || '').trim();
            const roomEntrance = (room.entrance || '').trim();
            const roomRoomNumber = (room.room_number || '').trim();
            const match = roomBuilding === building && 
                         roomEntrance === entrance && 
                         roomRoomNumber === roomNumber;
            if (match) {
            }
            return match;
        });


        if (!roomExists && building && entrance && roomNumber) {
            const errorHtml = `
                <div class="room-validation-error alert alert-danger mt-2" role="alert">
                    <i class="bi bi-exclamation-triangle-fill me-2"></i>
                    Комната ${building}-${entrance}-${roomNumber} не найдена в базе данных. 
                    Пожалуйста, сначала добавьте комнату в разделе "Управление комнатами".
                </div>
            `;

            const roomNumberInput = $('#room_number');
            const parentRow = roomNumberInput.closest('.row, .col-md-4, .form-group');
            
            if (parentRow.length) {
                const row = parentRow.closest('.row');
                if (row.length) {
                    row.after(errorHtml);
                } else {
                    const parentContainer = roomNumberInput.parent();
                    if (parentContainer.hasClass('col-md-4')) {
                        parentContainer.after(errorHtml);
                    } else {
                        $('#entrance').closest('.col-md-4').after(errorHtml);
                    }
                }
            } else {
                roomNumberInput.after(errorHtml);
            }

            return false;
        } else {
            return true;
        }
    },

    validateRoomBeforeSave(building, entrance, roomNumber) {
        if (!building || !entrance || !roomNumber) {
            return true;
        }

        if (!this.roomsLoaded) {
            $.ajax({
                url: '/api/rooms/list',
                async: false,
                success: (data) => {
                    if (data.success && data.rooms) {
                        this.availableRooms = data.rooms;
                        this.roomsLoaded = true;
                    }
                }
            });
        }

        const roomExists = this.availableRooms.some(room => {
            const roomBuilding = (room.building || '').trim();
            const roomEntrance = (room.entrance || '').trim();
            const roomRoomNumber = (room.room_number || '').trim();
            return roomBuilding === building && 
                   roomEntrance === entrance && 
                   roomRoomNumber === roomNumber;
        });

        if (!roomExists) {
            const errorMsg = `Ошибка: Комната ${building}-${entrance}-${roomNumber} не найдена в базе данных.\n\nПожалуйста, сначала добавьте комнату в разделе "Управление комнатами".`;
            alert(errorMsg);
            $('#room_number').focus();
            this.validateRoom();
            return false;
        }

        return true;
    }
};









