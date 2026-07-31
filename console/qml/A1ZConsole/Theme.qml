import QtQuick

QtObject {
    readonly property string fontFamily: Qt.platform.os === "osx"
                                         ? ".AppleSystemUIFont"
                                         : "Noto Sans CJK SC"

    // Pinned Apple light sRGB references. Pages consume semantic aliases only.
    readonly property color canvas: "#FFF2F2F7"
    readonly property color surface: "#FFFFFFFF"
    readonly property color surfaceRaised: "#FFFFFFFF"
    readonly property color mediaCanvas: "#FF1C1C1E"
    readonly property color logCanvas: "#FF1C1C1E"
    readonly property color control: "#FFF2F2F7"
    readonly property color controlHover: "#FFE5E5EA"
    readonly property color controlPressed: "#FFD1D1D6"
    readonly property color separator: "#FFE5E5EA"
    readonly property color separatorStrong: "#FFD1D1D6"
    readonly property color fill: "#33787880"

    readonly property color text: "#FF000000"
    readonly property color secondaryText: "#FF6C6C70"
    readonly property color tertiaryText: "#FF8E8E93"
    readonly property color placeholderText: "#FFAEAEB2"
    readonly property color textOnAccent: "#FFFFFFFF"
    readonly property color accent: "#FF007AFF"
    readonly property color accentFill: "#FF1E6EF4"
    readonly property color accentSoft: "#1F007AFF"
    readonly property color green: "#FF34C759"
    readonly property color greenSoft: "#1A34C759"
    readonly property color orange: "#FFFF8D28"
    readonly property color orangeSoft: "#1AFF8D28"
    readonly property color red: "#FFFF383C"
    readonly property color redFill: "#FFE9152D"
    readonly property color redSoft: "#1AFF383C"

    // Backwards-compatible surface aliases used by the existing pages.
    readonly property color windowTop: canvas
    readonly property color windowBottom: canvas
    readonly property color toolbar: surface
    readonly property color sidebar: surface
    readonly property color card: surface
    readonly property color cardRaised: surfaceRaised
    readonly property color tile: control
    readonly property color border: separator
    readonly property color borderStrong: separatorStrong
    readonly property color glassHighlight: "transparent"
    readonly property color cyan: accent
    readonly property color purple: accent

    readonly property int spacingXs: 4
    readonly property int spacingS: 8
    readonly property int spacingM: 12
    readonly property int spacingL: 16
    readonly property int spacingXl: 24
    readonly property int radiusSmall: 6
    readonly property int radiusControl: 8
    readonly property int radiusCard: 12
    readonly property int radiusPanel: 16
    readonly property int typeCaption: 12
    readonly property int typeLabel: 13
    readonly property int typeBody: 14
    readonly property int typeTitle: 17
    readonly property int typeHeading: 24
    readonly property int motionFast: 100
    readonly property int motionNormal: 140
}
