import type {Station} from "~/types/station.type";

export type StationSelection = {
  stations: Station[]
}

export type StationSelectionState = {
    selection: StationSelection
}
