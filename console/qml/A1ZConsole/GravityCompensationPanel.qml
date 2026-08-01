pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

GlassCard {
    id: root
    objectName: "gravityCompensationPanel"

    required property var controller
    property bool operationBlocked: false
    property real gravityFactorDraft: 1.0
    property bool gravityFactorDirty: false
    property string gravityDraftProfile: ""

    function synchronizeGravityFactorDraft() {
        if (gravityFactor.pressed)
            return

        const liveFactor = root.controller.gravityCompFactor
        if (root.gravityDraftProfile !== root.controller.profile) {
            root.gravityDraftProfile = root.controller.profile
            root.gravityFactorDraft = liveFactor
            root.gravityFactorDirty = false
            return
        }
        if (!root.gravityFactorDirty
                || Math.abs(root.gravityFactorDraft - liveFactor) < 0.001) {
            root.gravityFactorDraft = liveFactor
            root.gravityFactorDirty = false
        }
    }

    function discardGravityFactorDraft() {
        const liveFactor = root.controller.gravityCompFactor
        root.gravityFactorDraft = liveFactor
        root.gravityFactorDirty = false
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        SectionHeader {
            Layout.fillWidth: true
            theme: root.theme
            title: qsTr("重力补偿参数")
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Text {
                text: qsTr("补偿系数")
                color: root.theme.secondaryText
                font.family: root.theme.fontFamily
                font.pixelSize: root.theme.typeLabel
            }

            AppSlider {
                id: gravityFactor
                objectName: "gravityFactor"

                Layout.fillWidth: true
                theme: root.theme
                from: 0.0
                to: 1.0
                stepSize: 0.05
                value: root.gravityFactorDraft
                snapMode: Slider.SnapAlways
                enabled: root.controller.configurationEnabled
                Accessible.name: qsTr("重力补偿系数")
                onMoved: {
                    root.gravityFactorDraft = value
                    root.gravityFactorDirty = true
                }
            }

            Text {
                Layout.preferredWidth: 46
                text: gravityFactor.value.toFixed(2)
                color: root.theme.text
                horizontalAlignment: Text.AlignRight
                font.family: "monospace"
                font.pixelSize: root.theme.typeLabel
                font.weight: Font.DemiBold
            }

            AppButton {
                objectName: "applyGravityFactorButton"
                visible: root.controller.connected
                theme: root.theme
                text: qsTr("应用到 %1（重启）").arg(
                          root.controller.profile.toUpperCase())
                enabled: root.gravityFactorDirty
                         && root.controller.configurationEnabled
                         && !root.operationBlocked
                onClicked: root.controller.setGravityFactor(
                               root.gravityFactorDraft)
            }

            AppButton {
                objectName: "discardGravityFactorButton"
                visible: root.gravityFactorDirty
                theme: root.theme
                kind: "quiet"
                text: qsTr("放弃修改")
                enabled: !root.controller.commandBusy
                         && !root.controller.taskBusy
                         && !root.controller.emergencyBusy
                onClicked: root.discardGravityFactorDraft()
            }
        }

        Text {
            Layout.fillWidth: true
            text: root.operationBlocked
                  ? qsTr("有未发送控制目标；应用参数已锁定")
                  : qsTr("系数不热切换；应用会重启服务并回到位置保持。参数 · %1")
                    .arg(root.controller.dynamicsSummary)
            color: root.operationBlocked
                   ? root.theme.orange : root.theme.tertiaryText
            elide: Text.ElideRight
            font.family: root.theme.fontFamily
            font.pixelSize: root.theme.typeCaption
            AppToolTip {
                theme: root.theme
                visible: dynamicsHover.hovered && parent.truncated
                text: parent.text
            }

            HoverHandler {
                id: dynamicsHover
            }
        }
    }

    Connections {
        target: root.controller

        function onStateChanged() {
            root.synchronizeGravityFactorDraft()
        }
    }

    Component.onCompleted: root.synchronizeGravityFactorDraft()
}
