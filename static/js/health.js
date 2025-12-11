const Health = {
    getHealthInfo(emp) {
        const extra = emp.extra_data || {};
        const health = extra.health_info || { current: null, history: [] };
        return health;
    },

    isCurrentlyIll(emp) {
        const health = this.getHealthInfo(emp);
        return health.current && health.current.is_ill === true;
    },

};









