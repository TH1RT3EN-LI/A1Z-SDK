pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root

    required property var theme
    required property var controller
    required property string currentPage
    signal pageRequested(string route)

    implicitWidth: 190
    radius: root.theme.radiusPanel
    color: root.theme.sidebar

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: root.theme.spacingM
        spacing: root.theme.spacingXs

        Repeater {
            model: [
                { route: "overview", label: qsTr("运行总览"), icon: "activity" },
                { route: "manual", label: qsTr("手动操控"), icon: "sliders" },
                { route: "vision", label: qsTr("感知检查"), icon: "camera" },
                { route: "grasp", label: qsTr("自动抓取"), icon: "target" },
                { route: "teaching", label: qsTr("示教与回放"), icon: "record" },
                { route: "settings", label: qsTr("运行配置"), icon: "command" },
                { route: "diagnostics", label: qsTr("诊断与维护"), icon: "waveform" }
            ]

            NavButton {
                required property var modelData
                Layout.fillWidth: true
                theme: root.theme
                text: modelData.label
                iconName: modelData.icon
                selected: root.currentPage === modelData.route
                routeEnabled: modelData.route === "overview"
                              || modelData.route === "settings"
                              || modelData.route === "diagnostics"
                              || root.controller.startupReady
                blockedText: qsTr("启动引导尚未完成：%1")
                             .arg(root.controller.startupGateText)
                onClicked: {
                    if (routeEnabled)
                        root.pageRequested(modelData.route)
                    else
                        root.controller.explainStartupGate()
                }
            }
        }

        Item {
            Layout.fillHeight: true
        }
    }
}
