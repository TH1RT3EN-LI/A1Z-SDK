import QtQuick

QtObject {
    readonly property string fontFamily: Qt.platform.os === "osx"
                                         ? ".AppleSystemUIFont"
                                         : "Noto Sans CJK SC"

    readonly property color windowTop: "#171B22"
    readonly property color windowBottom: "#0D1015"
    readonly property color toolbar: "#E61E232C"
    readonly property color sidebar: "#D91A1F27"
    readonly property color card: "#F0222832"
    readonly property color cardRaised: "#FF2A313D"
    readonly property color tile: "#FF171C24"
    readonly property color control: "#FF303846"
    readonly property color controlHover: "#FF3A4555"
    readonly property color controlPressed: "#FF465365"
    readonly property color border: "#355F6B7B"
    readonly property color borderStrong: "#66758495"
    readonly property color glassHighlight: "#22FFFFFF"

    readonly property color text: "#FFF5F7FA"
    readonly property color secondaryText: "#FFB4BDC9"
    readonly property color tertiaryText: "#FF7E8998"
    readonly property color accent: "#FF35A7FF"
    readonly property color accentSoft: "#2935A7FF"
    readonly property color cyan: "#FF4BD7D0"
    readonly property color green: "#FF42D681"
    readonly property color greenSoft: "#2942D681"
    readonly property color orange: "#FFFFB454"
    readonly property color orangeSoft: "#29FFB454"
    readonly property color red: "#FFFF5F67"
    readonly property color redSoft: "#35FF5F67"
    readonly property color purple: "#FFC792EA"

    readonly property int spacingXs: 4
    readonly property int spacingS: 8
    readonly property int spacingM: 12
    readonly property int spacingL: 16
    readonly property int spacingXl: 22
    readonly property int radiusSmall: 6
    readonly property int radiusControl: 9
    readonly property int radiusCard: 13
    readonly property int radiusPanel: 16
    readonly property int typeCaption: 12
    readonly property int typeLabel: 14
    readonly property int typeBody: 15
    readonly property int typeTitle: 17
    readonly property int typeHeading: 23
}
