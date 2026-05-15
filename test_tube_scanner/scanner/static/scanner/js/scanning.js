
class ScannerManager {

    constructor(container, options = {}) {
        this.container = container;
        this.socket = null;
        this.debug_count = 0;
        
        this.ts = options.ts; 
        this.cx = options.cx; 
        this.cy = options.cy; 
        this.x  = options.x; 
        this.y  = options.y; 
        this.session = options.session; 
        this.scan_bt  = options.scan; 
        this.halt_bt    = options.halt; 
        this.debug   = options.debug; 
        this.median  = options.median; 
        this.crop    = options.crop; 
        this.speed_px_s   = options.speed_px_s; 
        this.axial_speed  = options.axial_speed; 
        this.axial_pos    = options.axial_pos; 
        this.area_px      = options.area_px; 
        this.frame_count  = options.frame_count; 
        this.scan_state   = options.scan_state;
        this.sim_bt       = options.simulate || null;
        this.well_btn     = options.well_btn;  
        this.well_state   = options.well_state;  
    }

    init_controls() {
        this.median.addEventListener('click',(e) => { this._send({ type: 'calibrate', topic: "median" }); });
        this.crop.addEventListener('click',  (e) => { this._send({ type: 'calibrate', topic: "crop" }); });
        this.scan_bt.addEventListener('click',  (e) => { this.scan(); });
        this.halt_bt.addEventListener('click',  (e) => { this.halt(); });
        
        if (this.sim_bt)  
            this.sim_bt.addEventListener('click',  (e) => { this.simulate(); });
    }

    registerSocket(socket)  {
        this.socket = socket;
        this.init_controls();
    }

    update(payload) {
        try {
            if (payload.jpeg)   { this.container.src = `data:image/jpeg;base64,${payload.jpeg}`; }
            if (payload.xy)     { this.x.textContent=payload.x.toFixed(2); this.y.textContent=payload.y.toFixed(2); }
            if (payload.state)  { 
                if (payload.state == 'median') {
                    const span = this.median.querySelector("span.median"); span.style.color = payload.value ? '#f0f' : '#fff';
                } else if (payload.state == 'crop') {
                    const span = this.crop.querySelector("span.crop"); span.style.color = payload.value ? '#f0f' : '#fff';
                }
                this.debug.insertAdjacentHTML('afterbegin', `<li>[ ${++this.debug_count} - ${payload.state} ]: ${payload.msg}</li>`); 
            }
            if (payload.ts)     { this.ts.textContent = timestampToLocalISOString(payload.ts); }
            if (payload.scan_state) { this.scan_state.textContent=payload.scan_state;}
            if (payload.well_state) { this.well_state.textContent=payload.well_state;}
                        
            if (payload.buttons) { 
                this.well_btn.innerHTML = payload.buttons; 
                const span = this.crop.querySelector("span.crop"); span.style.color = '#f0f';
            }
            if (payload.current >= 0) {                 
                document.querySelectorAll('button.w3-btn.well').forEach(btn => {
                    if (btn.value==payload.current) { btn.classList.add('w3-green'); return; }
                    btn.classList.remove('w3-green'); 
                });
            }                          
        } catch(e) { console.log(e); }
    }

    init()          { this.axes = 0;  this.cropping = 1; this._send({ type: 'scanner', topic: "init", });  }
    scan()          { this._send({ type: 'scanner', topic: "scan", session: this.session.value ? this.session.value: "0" }); }
    simulate()      { this._send({ type: 'scanner', topic: "simulate", session: this.session.value ? this.session.value: "0" }); }
    halt()          { this._send({ type: 'calibrate', topic: "halt" }); }

    _send(message)  { this.socket.send(message); }
}

class MetadataSocket {
    constructor(url) {
        this.url = url;
        this.ws = null;
        this.manager = null;
        this.reconnectDelay = 1000;
        this.shouldReconnect = true;
        this.reconnect = false;
    }

    setManager(manager) { this.manager = manager; }

    connect()           {
        this.ws = new WebSocket(this.url);

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.manager.update(data);
        };

        this.ws.onopen = (event) => {
            if (this.manager && !this.reconnect)
                this.manager['init']();
            this.reconnect = false;
        };

        this.ws.onclose = () => {
            console.warn(`WebSocket closed...`);
            if (this.shouldReconnect) {
                this.reconnect = true;
                setTimeout(() => {
                    console.log("Reconnect WebSocket...");
                    this.connect();
                }, this.reconnectDelay);
            }
        };
    }

    send(obj) { if (this.ws?.readyState === WebSocket.OPEN) { this.ws.send(JSON.stringify(obj));  } }
}