import * as L from 'leaflet';
import 'leaflet.markercluster';

export default defineNuxtPlugin((nuxtApp) => ({
    provide: {
        L,
    },
}));
